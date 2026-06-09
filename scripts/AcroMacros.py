"""
AcroMacros.py

The main AcroMacros class that ties together I/O, helper functions,
and callback management.
"""

import os
import re
import shutil
import traceback
from datetime import datetime
from uuid import uuid4
from typing import Any, Optional, Dict, List

from CallbacksExt import CallbacksExt
from AcroVersionExt import AcroVersionExt
from TDStoreTools import StorageManager

# Import I/O functions
from macro_io import (
    load_macro_data,
    write_macro_data,
    create_macro_folder_and_data,
    delete_folder
)
# Import helper functions from macro_helpers
from macro_helpers import (
    update_structure_order,
    remove_structure_entry,
    duplicate_macro_data,
    update_child_callbacks,
    normalize_path,
    update_sibling_order,
    find_path,
    select_macro_recursive,
)
# Import callback creation function
from macro_callbacks import create_callback_dat

TDF = op.TDModules.mod.TDFunctions


class AcroMacros(CallbacksExt, AcroVersionExt):
    """
    A system for controlling components via Macros.
    """

    def __init__(self, ownerComp: Any) -> None:
        """
        Initialize the AcroMacros extension.
        
        :param ownerComp: The component to which this extension is attached.
        """
        self.ownerComp = ownerComp
        self.callbackDat = self.ownerComp.par.Callbackdat.eval()

        try:
            super().__init__(ownerComp)
        except Exception:
            error_msg = traceback.format_exc()
            self.ownerComp.addScriptError(
                f"{error_msg} Error in CallbacksExt __init__. See textport."
            )
            print(f"Error initializing callbacks - {self.ownerComp.path}")
            print(error_msg)

        try:
            self.DoCallback('onInit', {'ownerComp': self.ownerComp})
        except Exception:
            error_msg = traceback.format_exc()
            self.ownerComp.addScriptError(
                f"{error_msg} Error in custom onInit callback. See textport."
            )
            print(error_msg)

        self.dataComp = ownerComp.op('data')
        self.macroCallbacksComp = ownerComp.op('macroCallbacks')

        # Clipboard for copy/cut operations.
        self.clipboard: Optional[str] = None
        self.cutMode: bool = False

        storedItems = [
            {'name': 'MacroData', 'default': {}, 'readOnly': False,
             'property': True, 'dependable': True},
            {'name': 'MacroStructure', 'default': [], 'readOnly': False,
             'property': True, 'dependable': True},
            {'name': 'SelectedMacro', 'default': '', 'readOnly': False,
             'property': True, 'dependable': True},
            {'name': 'Safety', 'default': False, 'readOnly': False,
             'property': True, 'dependable': True},
            {'name': 'Log', 'default': [], 'readOnly': False,
             'property': True, 'dependable': True},
            {'name': 'Signals', 'default': {}, 'readOnly': False,
             'property': True, 'dependable': True},
        ]
        self.stored = StorageManager(self, self.dataComp, storedItems)

        # initialize version extension
        AcroVersionExt.__init__(self, ownerComp)

        # Template path for callback generation
        self.callbacksTemplatesPath = os.path.join(
            var('ACRO_TD_MACROS'), 'scripts', 'CallbacksTemplates'
        )

        if self.ownerComp.par.Reloaddataonstart.eval():
            self.ReloadData(force=True)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _delayed_save(self, macro_uuid: str, delay: int = 2) -> None:
        """
        Schedule saving macro data with a delay.
        This ensures that changes have time to "cook" before saving.
        """
        run(self.SaveMacroData, macro_uuid, delayFrames=delay)

    def _verify_path_exists(self, path: str, on_success: callable,
                            on_failure: callable = None,
                            max_frames: int = 30) -> None:
        """
        Verify a path exists by polling every frame until found or timeout.
        Used to ensure OS file operations (rename, move) have completed
        before proceeding with dependent operations.

        Args:
            path: Path to check for existence
            on_success: Callback when path exists (no arguments)
            on_failure: Optional callback on timeout (receives path as argument)
            max_frames: Maximum frames to poll (~0.5 sec at 60fps by default)
        """
        attempt = [0]  # Mutable container for closure

        def check():
            if os.path.exists(path):
                on_success()
            elif attempt[0] < max_frames:
                attempt[0] += 1
                run(check, delayFrames=1)
            elif on_failure:
                on_failure(path)
            else:
                debug(f"_verify_path_exists timeout: {path}")

        run(check, delayFrames=1)

    def _get_caller_info(self) -> Dict:
        """
        Extract caller information from the traceback.
        """
        tb = traceback.extract_stack()
        is_emit = tb[-2].name == 'Emit'
        caller = tb[-2].filename
        caller_type = ''
        caller_name = caller
        if op(caller):
            caller_type = op(caller).type
            caller_name = caller
            if 'macroCallbacks' in op(caller).tags:
                caller_type = 'macro'
                caller_name = self.GetPathByUUID(caller.split('/')[-1])
        if is_emit:
            caller_name = tb[-3].filename
        del tb
        return {'caller': {'name': caller_name, 'type': caller_type}}

    # -------------------------------------------------------------------------
    # Core Methods
    # -------------------------------------------------------------------------

    def InitData(self, deleteFolders: bool = True) -> None:
        """
        Initialize all data by clearing storage and deleting callback DATs.
        Optionally delete macro folders on disk.
        """

        if deleteFolders:
            res = ui.messageBox('Confirm', f"Delete all macros and init all data!?!", buttons=['Ok', 'Cancel'])
            if res == 1:
                return

        self.stored['MacroData'] = {}
        self.stored['MacroStructure'] = []
        self.stored['Signals'] = {}

        for dat in self.macroCallbacksComp.findChildren(tags=['macroCallbacks']):
            try:
                dat.destroy()
            except Exception:
                self.ownerComp.addScriptError(
                    f"Error destroying DAT: {traceback.format_exc()}"
                )

        if deleteFolders:
            macros_path = self.ownerComp.par.Macrosfolder.eval()
            if os.path.exists(macros_path):
                delete_folder(macros_path)

    def ReloadData(self, force=False) -> None:
        """
        Reload all macros from disk, updating both macro data and structure.
        """
        if not force:
            res = ui.messageBox('Confirm', f"Reload macros from disk?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return

        self.InitData(deleteFolders=False)
        macros_path = self.ownerComp.par.Macrosfolder.eval()

        for root, dirs, files in os.walk(macros_path):
            rel_path = os.path.relpath(root, macros_path)
            if rel_path == '.':
                continue

            parts = rel_path.split(os.sep)
            parent_path = '' if len(parts) == 1 else os.path.join(*parts[:-1])
            name = parts[-1]

            file_path = os.path.join(root, 'data.json')
            if not os.path.exists(file_path):
                continue

            macroData = load_macro_data(file_path)
            if macroData is None:
                continue

            uid = macroData.get('uuid')
            if uid in self.stored['MacroData']:
                uid = uuid4().hex
                macroData['uuid'] = uid

            macroData['path'] = rel_path
            write_macro_data(file_path, macroData)
            self.stored['MacroData'][uid] = macroData

            macroStructure = {
                'uuid': uid,
                'name': name,
                'expanded': False,
                'selected': False,
                'error': False,
                'children': [],
            }

            if parent_path == '':
                self.stored['MacroStructure'].append(macroStructure)
            else:
                parent_structure = self.GetStructureByPath(parent_path)
                if parent_structure:
                    parent_structure['children'].append(macroStructure)

            textDat = self.macroCallbacksComp.create(textDAT, uid)
            textDat.par.language = 'python'
            textDat.par.file = os.path.join(root, 'callbacks.py')
            textDat.par.syncfile = True
            textDat.tags = ['macroCallbacks']

        self.stored['MacroStructure'] = update_structure_order(
            self.stored['MacroStructure'].copy(), self.stored['MacroData']
        )

    def GetPathByUUID(self, target_uuid: str) -> Optional[str]:
        """
        Return the full macro path as a string given its UUID.
        """
        return find_path(self.stored['MacroStructure'], target_uuid, [])

    def GetUUIDByPath(self, path: str) -> Optional[str]:
        """
        Get the UUID of a macro based on its path.
        """
        structure = self.GetStructureByPath(path)
        return structure.get('uuid') if structure else None

    def GetStructureByPath(self, path: str) -> Optional[Dict]:
        """
        Retrieve the macro structure dictionary corresponding to a given path.
        """
        norm_path = normalize_path(path)
        if not norm_path:
            return {'children': self.stored['MacroStructure']}
        parts = norm_path.split('/')
        current_level = self.stored['MacroStructure']
        found = None
        for part in parts:
            found = next((item for item in current_level if item['name'] == part), None)
            if not found:
                return None
            current_level = found.get('children', [])
        return found

    def getValidName(self, name: str, path: str) -> str:
        """
        Ensure the macro name is unique within the specified destination path.
        """
        macro_name = re.sub(r'[^a-zA-Z0-9_ -]', '', name)
        norm_path = normalize_path(path)
        if not norm_path:
            check_names = self.stored['MacroStructure']
        else:
            structure = self.GetStructureByPath(norm_path)
            check_names = structure.get('children', []) if structure else []
        if any(macro['name'] == macro_name for macro in check_names):
            i = 1
            while any(macro['name'] == f"{macro_name}_{i}" for macro in check_names):
                i += 1
            macro_name = f"{macro_name}_{i}"
        return macro_name

    def GetPathFromPathList(self, path_list: List[int]) -> str:
        """
        Convert a list of indices (representing a path in the macro structure)
        into a string path.
        """
        if not path_list:
            return ''
        structure = self.stored['MacroStructure'][path_list[0]]
        path = structure['name']
        for index in path_list[1:]:
            structure = structure['children'][index]
            path += '/' + structure['name']
        return path
    
    def GetPathListFromPath(self, path: str) -> List[int]:
        """
        Convert a string path into a list of indices representing the path in the macro structure.
        """
        norm_path = normalize_path(path)
        if not norm_path:
            return []
        parts = norm_path.split('/')
        current_level = self.stored['MacroStructure']
        path_list = []
        for part in parts:
            found = next((item for item in current_level if item['name'] == part), None)
            if not found:
                return []
            path_list.append(current_level.index(found))
            current_level = found.get('children', [])
        return path_list

    # -------------------------------------------------------------------------
    # Programmatic API (JSON-serializable returns for AcroMCP)
    # -------------------------------------------------------------------------

    def ListMacros(self) -> list:
        """
        Return a JSON-serializable list of all macros with key metadata.
        """
        result = []
        for uuid, data in self.stored['MacroData'].items():
            raw = data.getRaw()
            full_path = self.GetPathByUUID(uuid)
            structure = self.GetStructureByPath(full_path) if full_path else None
            result.append({
                'uuid': uuid,
                'name': raw.get('name', ''),
                'path': full_path or '',
                'comment': raw.get('comment', ''),
                'subscriptions': raw.get('subscriptions', []),
                'has_errors': bool(raw.get('errors', [])),
                'child_count': len(structure.get('children', [])) if structure else 0,
            })
        result.sort(key=lambda m: m['path'])
        return result

    def GetMacroInfo(self, path: str) -> Optional[Dict]:
        """
        Return full JSON-serializable info for a single macro by path.
        Returns None if the macro does not exist.
        """
        uuid = self.GetUUIDByPath(path)
        if not uuid:
            return None
        raw = self.stored['MacroData'][uuid].getRaw()
        structure = self.GetStructureByPath(path)
        return {
            'uuid': uuid,
            'name': raw.get('name', ''),
            'path': path,
            'comment': raw.get('comment', ''),
            'parameters': raw.get('parameters', {}),
            'subscriptions': raw.get('subscriptions', []),
            'errors': raw.get('errors', []),
            'children': [c['name'] for c in structure.get('children', [])] if structure else [],
        }

    def GetCallbackCode(self, path: str) -> Optional[str]:
        """
        Return the callback Python code for a macro by path.
        Returns None if the macro or its callback DAT does not exist.
        """
        uuid = self.GetUUIDByPath(path)
        if not uuid:
            return None
        callback_dat = self.macroCallbacksComp.op(uuid)
        if not callback_dat:
            return None
        return callback_dat.text

    def SetCallbackCode(self, path: str, code: str) -> Dict:
        """
        Set the callback Python code for a macro and save to disk.
        Re-validates the code and re-runs onInit to pick up subscription changes.
        """
        uuid = self.GetUUIDByPath(path)
        if not uuid:
            return {'ok': False, 'error': f'Macro not found: {path}'}
        callback_dat = self.macroCallbacksComp.op(uuid)
        if not callback_dat:
            return {'ok': False, 'error': f'Callback DAT not found for: {path}'}
        callback_dat.text = code
        # Save to disk directly for reliability
        macros_path = self.ownerComp.par.Macrosfolder.eval()
        full_path = self.GetPathByUUID(uuid)
        file_path = os.path.join(macros_path, *full_path.split('/'), 'callbacks.py')
        abs_path = os.path.join(project.folder, file_path)
        with open(abs_path, 'w', newline='\n') as f:
            f.write(code)
        self.UpdateMacroCallbacks(uuid)
        return {'ok': True, 'path': path}

    def SetMacroComment(self, path: str, comment: str) -> Dict:
        """
        Set the comment for a macro by path.
        """
        uuid = self.GetUUIDByPath(path)
        if not uuid:
            return {'ok': False, 'error': f'Macro not found: {path}'}
        self.stored['MacroData'][uuid]['comment'] = comment
        self._delayed_save(uuid)
        return {'ok': True, 'path': path}

    def GetSignals(self) -> Dict:
        """
        Return the signal routing table as a JSON-serializable dict.
        Keys are signal names, values are lists of subscribed macro paths.
        """
        result = {}
        for signal_name in self.stored['Signals']:
            val = self.stored['Signals'][signal_name]
            result[signal_name] = val.getRaw() if hasattr(val, 'getRaw') else list(val)
        return result

    def SaveMacroData(self, macro_uuid: str) -> None:
        """
        Save the macro data (JSON) for the given UUID to disk.
        """
        # Guard: Skip if macro was deleted while save was pending
        if macro_uuid not in self.stored['MacroData']:
            debug(f"SaveMacroData skipped - macro deleted: {macro_uuid}")
            return

        macroData = self.stored['MacroData'][macro_uuid].getRaw()
        path = self.GetPathByUUID(macro_uuid)
        macros_path = self.ownerComp.par.Macrosfolder.eval()
        folder_path = os.path.join(macros_path, *path.split('/'))

        # Guard: Skip if folder doesn't exist (move/rename in progress)
        if not os.path.exists(folder_path):
            debug(f"SaveMacroData skipped - folder missing: {folder_path}")
            return

        file_path = os.path.join(folder_path, 'data.json')
        write_macro_data(file_path, macroData)

    def AddMacro(self) -> None:
        """
        Create a new macro at the currently selected path.
        """
        path = self.GetPathByUUID(self.stored['SelectedMacro'])
        if not path:
            path = '/'
        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Add Macro: {path}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
        self.CreateMacro('New Macro', path)

    def CreateMacro(self, name: str, path: str) -> None:
        """
        Create a new macro with the specified name and path.
        """
        name = re.sub(r'[^a-zA-Z0-9_ -]', '', name)
        structure = self.GetStructureByPath(path)
        if structure is None:
            return

        # Get the list of macros in the current scope.
        if path in ['', '/']:
            check_names = structure.get('children', [])
        else:
            check_names = structure['children']
            structure['expanded'] = True

        if any(macro['name'] == name for macro in check_names):
            i = 1
            while any(macro['name'] == f"{name}_{i}" for macro in check_names):
                i += 1
            name = f"{name}_{i}"

        new_uuid = uuid4().hex
        macro_structure = {
            'uuid': new_uuid,
            'name': name,
            'expanded': False,
            'selected': False,
            'error': False,
            'children': [],
        }

        norm_path = normalize_path(path)
        path_parts = norm_path.split('/') if norm_path else []

        # Insert the new macro into the appropriate structure.
        if not norm_path:
            order = len(self.stored['MacroStructure'])
            self.stored['MacroStructure'].append(macro_structure)
        else:
            parent_structure = self.GetStructureByPath(norm_path)
            order = len(parent_structure['children'])
            parent_structure['children'].append(macro_structure)

        macro_data = {
            'uuid': new_uuid,
            'name': name,
            'path': norm_path,
            'order': order,
            'comment': '',
            'parameters': {},
            'subscriptions': [],
            'errors': [],
            'log': [],
        }
        self.stored['MacroData'][new_uuid] = macro_data

        macros_path = self.ownerComp.par.Macrosfolder.eval()
        child_path = os.path.join(macros_path, *path_parts)
        folder_path = os.path.join(child_path, name)
        create_macro_folder_and_data(folder_path, macro_data)

        create_callback_dat(
            self.macroCallbacksComp,
            textDAT,
            new_uuid,
            folder_path,
            self.callbacksTemplatesPath
        )
        self.UpdateMacroCallbacks(new_uuid)

    def DeleteSelected(self) -> None:
        """
        Delete the currently selected macro.
        """
        path = self.GetPathByUUID(self.stored['SelectedMacro'])
        if not path:
            return

        self.DeleteMacro(path)

    def DeleteMacro(self, macro: str) -> None:
        """
        Delete a macro (and its associated data) given its path.
        """
        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Delete macro: {macro}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
            
        macro_uuid = self.GetUUIDByPath(macro)
        if not macro_uuid:
            return

        self.stored['MacroData'].pop(macro_uuid, None)
        remove_structure_entry(self.stored['MacroStructure'], macro_uuid)

        macros_path = self.ownerComp.par.Macrosfolder.eval()
        folder_path = os.path.join(macros_path, *macro.split('/'))
        if os.path.exists(folder_path):
            delete_folder(folder_path)

        callbackDat = self.macroCallbacksComp.op(macro_uuid)
        if callbackDat:
            try:
                callbackDat.destroy()
            except Exception:
                self.ownerComp.addScriptError(
                    f"Error destroying callback DAT: {traceback.format_exc()}"
                )

        parent_path = '/'.join(macro.split('/')[:-1])
        parent_structure = self.GetStructureByPath(parent_path)
        if parent_path and isinstance(parent_structure, dict):
            parent_children = parent_structure.get('children', [])
        else:
            parent_children = self.stored['MacroStructure']
        for i, child in enumerate(parent_children):
            uid = child['uuid']
            self.stored['MacroData'][uid]['order'] = i
            self._delayed_save(uid)


    def CopyMacro(self, macro: str) -> None:
        """
        Copy a macro to the clipboard.
        """
        ui.clipboard = macro
        self.clipboard = macro
        self.cutMode = False

    def CutMacro(self, macro: str) -> None:
        """
        Cut a macro to the clipboard.
        """
        ui.clipboard = macro
        self.clipboard = macro
        self.cutMode = True

    def PasteMacro(self, dest_path: str) -> None:
        """
        Paste a macro from the clipboard to a destination path.
        """
        if not self.clipboard:
            print("No macro in clipboard")
            return

        src_path = self.clipboard
        if not src_path:
            print("No path for macro in clipboard")
            return

        if '/'.join(dest_path.split('/')[:-1]).startswith(src_path):
            print("Cannot paste into same parent folder")
            return
        print(src_path)
        if self.cutMode:
            src_pathlist = self.GetPathListFromPath(src_path)
            dest_pathlist = self.GetPathListFromPath(dest_path)
            self.MoveMacro(src_pathlist, dest_pathlist, 'under')
        else:
            self.copyMacro('/'.join(dest_path.split('/')))#[:-1]))

    def copyMacro(self, dest_path: str) -> None:
        """
        Create a copy of a macro on disk in a new path.
        New UUIDs are generated for the copied macros.
        """
        structure_copy = self.GetStructureByPath(self.clipboard).getRaw()
        src_path = self.clipboard

        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Copy macro: {src_path} to {dest_path}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
            
        src_macro_data = self.stored['MacroData'][self.GetUUIDByPath(self.clipboard)].getRaw()
        name = src_macro_data['name']
        name = self.getValidName(name, dest_path)
        structure_copy['name'] = name
        structure_copy['selected'] = False

        macros_path = self.ownerComp.par.Macrosfolder.eval()
        folder_path = os.path.join(macros_path, *src_path.split('/'))
        new_folder_path = os.path.join(macros_path, *dest_path.split('/'), name)
        shutil.copytree(folder_path, new_folder_path)
        duplicate_macro_data([structure_copy], dest_path + '/' + name, name, self.stored['MacroData'])
        order = src_macro_data['order'] + 1

        if dest_path == '':
            new_parent_children = self.stored['MacroStructure']
            new_parent_children.insert(order, structure_copy)
        else:
            new_parent_structure = self.GetStructureByPath(dest_path)
            new_parent_children = new_parent_structure['children']
            new_parent_children.insert(order, structure_copy)

        for i, child in enumerate(new_parent_children):
            uid = child['uuid']
            self.stored['MacroData'][uid]['order'] = i

        self._create_callback_dats_for_copy(structure_copy, dest_path)

    def _create_callback_dats_for_copy(self, structure: Dict, dest_path: str) -> None:
        """
        Recursively create callback DATs for a copied macro structure.
        """
        macros_path = self.ownerComp.par.Macrosfolder.eval()

        def _create_recursive(data: List[Dict], current_path: str) -> None:
            for macro in data:
                uid = macro['uuid']
                new_path = f"{current_path}/{macro['name']}"
                file_path = os.path.join(macros_path, *new_path.split('/'), 'callbacks.py')
                textDat = self.macroCallbacksComp.create(textDAT, uid)
                textDat.par.language = 'python'
                textDat.par.file = file_path
                textDat.par.syncfile = True
                textDat.tags.add('macroCallbacks')
                self._delayed_save(uid)
                _create_recursive(macro.get('children', []), new_path)
        _create_recursive([structure], dest_path)

    def MoveMacro(self, from_path_list: List[int], to_path_list: List[int],
                  move_type: str, copy: bool = False) -> None:
        """
        Move a macro from one location to another.
        
        Steps:
         1. Convert path lists to string paths.
         2. Update the macro's stored path.
         3. Compute source and destination folder paths.
         4. Check for name conflicts in the destination; if a conflict exists,
            generate a new unique name and update the macro's data.
         5. Update callback DAT file paths (for parent and children).
         6. Schedule the folder move.
         7. Update the in-memory macro structure and sibling order.
        
        :param from_path_list: List of integers representing the source path indices.
        :param to_path_list: List of integers representing the destination path indices.
        :param move_type: Move type; e.g., 'above', 'below', or 'under'.
        :param copy: If True, perform a copy instead of a move.
        """
        # Step 1: Convert path lists to string paths.
        from_path = self.GetPathFromPathList(from_path_list)
        if move_type in ['above', 'below']:
            to_path = self.GetPathFromPathList(to_path_list[:-1])
            to_index = to_path_list[-1]
            if move_type == 'below':
                to_index += 1
        else:
            to_path = self.GetPathFromPathList(to_path_list)
            to_index = 0

        # if safety is on, prompt user for confirmation.
        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Move macro: {from_path} to {to_path}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
            
        # Step 2: Retrieve macro data and update its stored path.
        from_uuid = self.GetUUIDByPath(from_path)
        if not from_uuid:
            return
        macro_data = self.stored['MacroData'][from_uuid]
        macro_data['path'] = to_path

        # Step 3: Compute folder paths.
        macros_path = self.ownerComp.par.Macrosfolder.eval()
        from_folder_path = os.path.join(macros_path, *from_path.split('/'))
        macro_name = macro_data['name']
        to_folder_path = os.path.join(macros_path, *to_path.split('/'), macro_name)

        # Step 4: Check for name conflicts in the destination.
        dest_parent = self.GetStructureByPath(to_path)
        if dest_parent is None:
            # At the root level.
            dest_children = self.stored['MacroStructure']
        else:
            dest_children = dest_parent.get('children', [])
        
        # skip renaming if the destination is the same as the source, we're just reordering.
        if not copy and '/'.join(from_path.split('/')[:-1]) == to_path:
            pass

        elif any(child['name'] == macro_name for child in dest_children):
            # Conflict detected; generate a new unique name.
            new_name = self.getValidName(macro_name, to_path)
            macro_data['name'] = new_name
            # Also update the macro structure.
            old_parent_path = '/'.join(from_path.split('/')[:-1])
            old_parent_structure = self.GetStructureByPath(old_parent_path)
            if old_parent_structure:
                for child in old_parent_structure.get('children', []):
                    if child['uuid'] == from_uuid:
                        child['name'] = new_name
                        break
            macro_name = new_name
            # Recompute destination folder path with the new name.
            to_folder_path = os.path.join(macros_path, *to_path.split('/'), macro_name)

        # Step 5: Update callback DAT file paths.
        try:
            # Update parent's callback DAT.
            callback_dat = self.macroCallbacksComp.op(from_uuid)
            if callback_dat:
                callback_dat.par.file = os.path.join(to_folder_path, 'callbacks.py')
            # Find the macro structure in the old parent's children.
            macro_structure = None
            old_parent_path = '/'.join(from_path.split('/')[:-1])
            old_parent_structure = self.GetStructureByPath(old_parent_path)
            if old_parent_path:
                old_children = old_parent_structure['children']
            else:
                old_children = self.stored['MacroStructure']
            for macro in old_children:
                if macro['uuid'] == from_uuid:
                    macro_structure = macro
                    break
            # Recursively update callback DAT paths for children.
            if macro_structure:
                update_child_callbacks(macro_structure, to_folder_path, self.macroCallbacksComp)
            # Step 6: Schedule the folder move with a delay (skip if just reordering).
            if from_folder_path != to_folder_path:
                run(os.rename, from_folder_path, to_folder_path, delayFrames=2)
        except Exception:
            self.ownerComp.addScriptError(
                f"Error moving folder from {from_folder_path} to {to_folder_path}: {traceback.format_exc()}"
            )

        # Step 7: Update the in-memory macro structure.
        # Remove from the old parent's children.
        old_parent_path = '/'.join(from_path.split('/')[:-1])
        old_parent_structure = self.GetStructureByPath(old_parent_path)
        if old_parent_path:
            old_children = old_parent_structure['children']
        else:
            old_children = self.stored['MacroStructure']
        macro_structure = None
        for macro in old_children:
            if macro['uuid'] == from_uuid:
                macro_structure = macro
                old_children.remove(macro)
                break
        if macro_structure is None:
            return

        # Insert into the new parent's children at the specified index.
        new_parent_structure = self.GetStructureByPath(to_path)
        if new_parent_structure is None:
            new_children = self.stored['MacroStructure']
        else:
            new_children = new_parent_structure.get('children', [])
            new_parent_structure['expanded'] = True
        new_children.insert(to_index, macro_structure)

        # Update sibling order in both old and new parent's children.
        update_sibling_order(old_children, self.stored)
        update_sibling_order(new_children, self.stored)

        # Check if this is just a reorder (same folder path) vs actual move
        is_reorder = (from_folder_path == to_folder_path)

        if is_reorder:
            # Just reordering within same parent - no folder move needed
            # Save the macro and all affected siblings
            self._delayed_save(from_uuid)
            for sibling in new_children:
                if sibling['uuid'] != from_uuid:
                    self._delayed_save(sibling['uuid'])
        else:
            # Actual move - verify folder move completed before saving data
            def on_move_complete():
                self._delayed_save(from_uuid)

            def on_move_failed(path):
                self.ownerComp.addScriptError(
                    f"MoveMacro: folder not found at {path} after 60 frames"
                )

            self._verify_path_exists(
                path=to_folder_path,
                on_success=on_move_complete,
                on_failure=on_move_failed,
                max_frames=60  # ~1 second at 60fps
            )

    def TriggerSelected(self, args: Any = None, delayMilliSeconds: int = 0,
                        delayFrames: int = 0) -> None:
        """
        Trigger the currently selected macro.
        If safety is enabled, prompt for confirmation.
        """
        path = self.GetPathByUUID(self.stored['SelectedMacro'])
        if not path:
            return
        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Trigger macro: {path}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
        self.TriggerMacro(path, args, delayMilliSeconds, delayFrames)

    def ToggleSafety(self) -> None:
        """
        Toggle safety mode on or off.
        """
        self.stored['Safety'] = not self.stored['Safety']

    def TriggerMacro(self, macro_path: str, args: Any = None,
                     delayMilliSeconds: int = 0, delayFrames: int = 0) -> None:
        """
        Trigger a macro by its path.
        Extracts caller info, logs the trigger, and schedules execution.
        """
        caller_info = self._get_caller_info()
        info = {
            **caller_info,
            'delayMilliSeconds': delayMilliSeconds,
            'delayFrames': delayFrames,
        }
        macro_uuid = self.GetUUIDByPath(macro_path)
        trigger_type = 'emit' if info['caller']['name'] == 'emit' else 'trigger'
        self.AddMacroLog(macro_uuid, {'type': trigger_type, 'args': args, 'info': info})
        run(
            self.triggerMacro,
            macro_uuid,
            info,
            self.ownerComp,
            self.stored['MacroData'][macro_uuid].getRaw(),
            op.comps,
            args,
            delayFrames=delayFrames,
            delayMilliSeconds=delayMilliSeconds
        )

    def triggerMacro(self, macro_uuid: str, info: Dict, mc: Any, macro: Dict,
                     comps: Any, args: Any) -> None:
        """
        Handler for executing a macro's trigger function.
        """
        try:
            self.macroCallbacksComp.op(macro_uuid).module.onTrigger(info, mc, macro, comps, args)
        except Exception:
            error_msg = traceback.format_exc()
            self.ownerComp.addScriptError("Error in Callback DAT. See textport for details.")
            path = self.GetPathByUUID(macro_uuid)
            structure = self.GetStructureByPath(path)
            if structure:
                structure['error'] = True
            self.AddMacroError(macro_uuid, error_msg)
        self.DoCallback('onTriggerMacro', {'info': info, 'macro': macro, 'args': args})

    def RenameMacroUUID(self, uuid_val: str, name: str) -> None:
        """
        Rename a macro given its UUID.
        Updates both stored data and the physical folder.
        """
        # macro name can not be empty.
        if len(name) < 1:
            debug("Macro name can not be empty.")
            return
        
        path = self.GetPathByUUID(uuid_val)
        name = self.getValidName(name, '/'.join(path.split('/')[:-1]))

        # check if safety is on, prompt user for confirmation.
        if self.stored['Safety']:
            res = ui.messageBox('Confirm', f"Rename macro: {path} to {name}?", buttons=['Ok', 'Cancel'])
            if res == 1:
                return
        
        # change name in macro data and structure (in-memory only, don't save yet)
        macroData = self.stored['MacroData'][uuid_val]
        macroData['name'] = name
        structure = self.GetStructureByPath(path)
        if structure:
            structure['name'] = name

        # get path of macros folder
        macrosfolder_filepath = self.ownerComp.par.Macrosfolder.eval()

        # get old and new macro folder paths on disk
        old_macro_filepath = os.path.join(macrosfolder_filepath, *path.split('/'))
        new_macro_filepath = os.path.join(macrosfolder_filepath, *path.split('/')[:-1], name)

        # get old and new macro path
        old_macro_path = path
        new_macro_path = '/'.join(path.split('/')[:-1] + [name])

        # Update callback DAT path to new location (releases file handles)
        callback_dat = self.macroCallbacksComp.op(uuid_val)
        if callback_dat:
            callback_dat.par.file = os.path.join(new_macro_filepath, 'callbacks.py')

        # Collect child UUIDs for saving after rename completes
        child_uuids = []

        def update_children_paths(data: List[Dict], parent_filepath: str, parent_path: str) -> None:
            """Update callback DAT paths and collect UUIDs (in-memory only, no saves yet)"""
            for macro in data:
                uid = macro['uuid']
                macro_name = macro['name']
                new_filepath = f"{parent_filepath}/{macro_name}"
                new_path = f"{parent_path}/{macro_name}"
                self.macroCallbacksComp.op(uid).par.file = new_filepath + '/callbacks.py'
                child_macro_data = self.stored['MacroData'][uid]
                child_macro_data['path'] = parent_path
                child_uuids.append(uid)
                update_children_paths(macro.get('children', []), new_filepath, new_path)

        update_children_paths(structure.get('children', []), new_macro_filepath, new_macro_path)

        # Schedule folder rename
        run(os.rename, old_macro_filepath, new_macro_filepath, delayFrames=1)

        # Verify rename completed, THEN save all data
        def on_rename_complete():
            # Save parent data to NEW location
            self.SaveMacroData(uuid_val)
            # Save all children
            for uid in child_uuids:
                self._delayed_save(uid, delay=2)

        def on_rename_failed(failed_path):
            self.ownerComp.addScriptError(
                f"RenameMacro: folder not found at {failed_path} after 30 frames"
            )

        self._verify_path_exists(
            path=new_macro_filepath,
            on_success=on_rename_complete,
            on_failure=on_rename_failed,
            max_frames=30
        )

    def RenameMacroPath(self, path: str, name: str) -> None:
        """
        Rename a macro given its path.
        """
        macro_uuid = self.GetUUIDByPath(path)
        if macro_uuid:
            self.RenameMacroUUID(macro_uuid, name)

    def SelectMacro(self, macro_uuid: str) -> None:
        """
        Mark a macro as selected given its UUID.
        """
        select_macro_recursive(self.stored['MacroStructure'], macro_uuid)
        self.stored['SelectedMacro'] = macro_uuid

    def ClearMacroErrors(self, macro_uuid: str) -> None:
        """
        Clear error logs for a macro.
        """
        macroData = self.stored['MacroData'][macro_uuid]
        macroData['errors'] = []
        path = self.GetPathByUUID(macro_uuid)
        structure = self.GetStructureByPath(path)
        if structure:
            structure['error'] = False

    def UpdateMacroCallbacks(self, macro_uuid: str) -> None:
        """
        Update a macro's callback DAT by verifying its contents and reinitializing it.
        """
        callbackDat = self.macroCallbacksComp.op(macro_uuid)
        path = self.GetPathByUUID(macro_uuid)
        structure = self.GetStructureByPath(path)
        try:
            if callbackDat.text.strip():
                _ = callbackDat.module
            if structure:
                structure['error'] = False
        except Exception:
            error_msg = traceback.format_exc()
            self.ownerComp.addScriptError("Error in Callback DAT. See textport for details.")
            if structure:
                structure['error'] = True
            self.AddMacroError(macro_uuid, error_msg)
        self.stored['MacroData'][macro_uuid]['subscriptions'] = []
        info = {}
        callbackDat.module.onInit(info, self.ownerComp, self.stored['MacroData'][macro_uuid].getRaw())

    def AddMacroLog(self, macro_uuid: str, log: Dict) -> None:
        """
        Add a log entry for a specific macro.
        """
        macroData = self.stored['MacroData'][macro_uuid]
        log_entry = {
            'log': log,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        log_type = log['type']
        log_args = log['args']
        log_info = log['info']
        log_time = log_entry['time']
        log_caller_name = log_info['caller']['name']
        log_caller_type = log_info['caller']['type']
        log_delayms = log_info['delayMilliSeconds']
        log_delayf = log_info['delayFrames']
        formatted_log = (
            f"{log_time} | Type: {log_type} | Args: {log_args} | "
            f"Caller: {log_caller_name}:{log_caller_type} | Delay: {log_delayms}(ms) {log_delayf}(f)"
        )
        macroData['log'].insert(0, formatted_log)
        macroData['log'] = macroData['log'].getRaw()[:100]
        macro_path = self.GetPathByUUID(macro_uuid)
        info_log = (
            f"Type: {log_type} | Args: {log_args} | "
            f"Caller: {log_caller_name}:{log_caller_type} | Delay: {log_delayms}(ms) {log_delayf}(f)"
        )
        self.AddLog(f"INFO | {log_time} | TRIGGER | {macro_path} | {info_log}", 'INFO')

    def ClearMacroLog(self, macro_uuid: str) -> None:
        """
        Clear the log for a specific macro.
        """
        macroData = self.stored['MacroData'][macro_uuid]
        macroData['log'] = []

    def AddLog(self, log: str, level: str = 'INFO') -> None:
        """
        Add a global log entry.
        """
        self.stored['Log'].insert(0, log)
        self.stored['Log'] = self.stored['Log'].getRaw()[:100]
        if self.ownerComp.par.Logtofile.eval():
            match level:
                case 'INFO':
                    op.Logger.Info(log)
                case 'WARNING':
                    op.Logger.Warning(log)
                case 'ERROR':
                    op.Logger.Error(log)
                case _:
                    op.Logger.Info(log)

    def ClearLog(self) -> None:
        """
        Clear all global log entries.
        """
        self.stored['Log'] = []

    def AddMacroError(self, macro_uuid: str, error: str) -> None:
        """
        Add an error entry for a specific macro.
        """
        errors = error.split('\n')[-3:-1]
        if errors:
            errors[0] = ','.join(errors[0].split(',')[1:])
        error_data = {
            'traceback': error,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': ' | '.join(errors)
        }
        error_info = f"{error_data['time']} | {error_data['error']}"
        self.stored['MacroData'][macro_uuid]['errors'].insert(0, error_info)
        self.stored['MacroData'][macro_uuid]['errors'] = (
            self.stored['MacroData'][macro_uuid]['errors'].getRaw()[:100]
        )
        macro_path = self.GetPathByUUID(macro_uuid)
        self.AddLog(f"ERROR | {macro_path} | {error_info}", 'ERROR')

    def Emit(self, signal: str, args: Any = None) -> None:
        """
        Emit a signal to trigger all macros subscribed to it.
        """
        time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.AddLog(f"INFO | {time} | EMIT | Signal: {signal} | Caller: {self._get_caller_info()['caller']['name']} | Args: {args}", 'INFO')

        for macro in self.stored['MacroData'].values():
            if signal in macro['subscriptions']:
                uid = self.GetPathByUUID(macro['uuid'])
                self.TriggerMacro(uid, args)
        
        self.DoCallback('onEmit', {'signal': signal, 'args': args})

    def Subscribe(self, macro: Dict, signal: str) -> None:
        """
        Subscribe a macro to a signal and update the subscriptions dictionary.
        """
        macro_uuid = macro['uuid']
        macro_path = self.GetPathByUUID(macro_uuid)

        # Add the signal to the macro's subscriptions
        if signal not in self.stored['MacroData'][macro_uuid]['subscriptions']:
            self.stored['MacroData'][macro_uuid]['subscriptions'].append(signal)
            self.SaveMacroData(macro_uuid)

        # # Update the global subscriptions dictionary
        # if signal not in self.stored['Subscriptions']:
        #     self.stored['Subscriptions'][signal] = []
        # if macro_path not in self.stored['Subscriptions'][signal]:
        #     self.stored['Subscriptions'][signal].append(macro_path)

        self.UpdateSignals()

    def UpdateSignals(self) -> None:
        """
        Update the signals dictionary for all macros.
        """
        self.stored['Signals'] = {}
        for macro in self.stored['MacroData'].values():
            for signal in macro['subscriptions']:
                if signal not in self.stored['Signals']:
                    self.stored['Signals'][signal] = []
                path = self.GetPathByUUID(macro['uuid'])
                if path not in self.stored['Signals'][signal]:
                    self.stored['Signals'][signal].append(path)

    def pulse_Editextension(self) -> None:
        """
        Pulse the parameter to open the extension interface.
        """
        self.ownerComp.op('AcroMacros').par.edit.pulse()

    def pulse_Initdata(self) -> None:
        """
        Pulse the parameter to initialize data.
        """
        self.InitData()

    def pulse_Reloaddata(self) -> None:
        """
        Pulse the parameter to reload data.
        """
        self.ReloadData()
