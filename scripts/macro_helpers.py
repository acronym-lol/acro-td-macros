"""
macro_helpers.py

Contains helper functions for recursive operations such as updating structure order,
removing structure entries, and duplicating macro data.
"""
import os
import traceback
from typing import List, Dict, Any, Optional
from uuid import uuid4


def update_structure_order(structure_list: List[Dict], macro_data: Dict) -> List[Dict]:
    """
    Recursively update macro structure order based on stored macro data.
    """
    macros_list = []
    for i, macro in enumerate(structure_list):
        uid = macro['uuid']
        order = macro_data.get(uid, {}).get('order', i)
        macros_list.append((i, order))
        if macro.get('children'):
            macro['children'] = update_structure_order(macro['children'], macro_data)
    macros_list.sort(key=lambda x: x[1])
    return [structure_list[i] for i, _ in macros_list]


def remove_structure_entry(data: List[Dict], target_uuid: str) -> bool:
    """
    Recursively remove a macro structure entry by UUID.
    """
    for entry in data:
        if entry.get('uuid') == target_uuid:
            data.remove(entry)
            return True
        if remove_structure_entry(entry.get('children', []), target_uuid):
            return True
    return False


def duplicate_macro_data(
    data: List[Dict], current_path: str, base_name: str, macro_store: Dict
) -> None:
    """
    Recursively duplicate macro data for copy operations.
    
    :param data: List of macro structure entries to duplicate.
    :param current_path: The new path for the duplicated macros.
    :param base_name: Base name used for constructing the new path.
    :param macro_store: The dictionary holding macro data (e.g., from TDStoreTools).
    """
    for entry in data:
        # Assuming each stored macro has a getRaw() method as used by TDStoreTools.
        macro_data = macro_store[entry['uuid']].getRaw()
        new_uuid = uuid4().hex
        entry['uuid'] = new_uuid
        macro_data['path'] = current_path
        macro_data['name'] = entry['name']
        macro_data['uuid'] = new_uuid
        macro_store[new_uuid] = macro_data
        duplicate_macro_data(
            entry.get('children', []),
            f"{current_path}/{base_name}",
            base_name,
            macro_store
        )
       
def update_child_callbacks(macro_structure: Dict, new_base: str, macroCallbacksComp: Any) -> None:
    """
    Recursively update the file parameter of callback DATs for the children of the given macro structure.
    
    This function assumes that the parent's callback DAT file has already been updated.
    The new base passed in represents the destination folder for the parent macro.
    It then updates each child to have its file path set to:
    new_base / parent's name / child's name / callbacks.py
    """
    #parent_name = macro_structure.get('name', '')
    for child in macro_structure.get('children', []):
        child_uuid = child['uuid']
        child_callback_dat = macroCallbacksComp.op(child_uuid)
        new_path = os.path.join(new_base, child['name'])
        if child_callback_dat:
            new_child_path = normalize_path(os.path.join(new_path, 'callbacks.py'))
            child_callback_dat.par.file = new_child_path
        # For the child's children, the new base becomes new_base/parent_name.
        update_child_callbacks(child, normalize_path(new_path), macroCallbacksComp)

def normalize_path(path: str) -> str:
    """
    Normalize a path by converting backslashes to forward slashes
    and trimming leading/trailing whitespace and slashes.
    """
    return path.replace('\\', '/').strip().strip('/')

def update_sibling_order(siblings: List[Dict], stored: Any) -> List:
    """
    Update the order of sibling macros and schedule their save.
    """
    updated_siblings = []
    for i, child in enumerate(siblings):
        uid = child['uuid']
        stored['MacroData'][uid]['order'] = i
        updated_siblings.append(uid)
    return updated_siblings

def find_path(data: List[Dict], target: str, current_path: List[str]) -> Optional[str]:
    """
    Recursively find a macro's path by UUID.
    """
    for entry in data:
        if entry.get('uuid') == target:
            return '/'.join(current_path + [entry.get('name')])
        result = find_path(entry.get('children', []), target, current_path + [entry.get('name')])
        if result:
            return result
    return None

def select_macro_recursive(data: List[Dict], target: str) -> None:
    """
    Recursively set the 'selected' flag for the target macro.
    """
    for entry in data:
        entry['selected'] = (entry.get('uuid') == target)
        select_macro_recursive(entry.get('children', []), target)

