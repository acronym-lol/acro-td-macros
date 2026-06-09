"""
macro_callbacks.py

Handles creation and management of callback DATs using a Jinja2 template.
"""

import os
import traceback
from jinja2 import Environment, FileSystemLoader
from typing import Any

def create_callback_dat(
    macroCallbacksComp: Any,
    textDAT: Any,
    macro_uuid: str,
    folder_path: str,
    template_path: str
) -> None:
    """
    Create a callback DAT using a Jinja2 template.
    
    :param macroCallbacksComp: The component managing callback DATs.
    :param textDAT: The text DAT type (used by TD environment).
    :param macro_uuid: The UUID of the macro.
    :param folder_path: The folder where the macro resides.
    :param template_path: Path to the folder containing the Jinja2 template.
    """
    try:
        file_loader = FileSystemLoader(template_path)
        env = Environment(loader=file_loader)
        template = env.get_template('MacroCallbacksTemplate.py.j2')
        output = template.render()
        callbacks_file_path = os.path.join(folder_path, 'callbacks.py')
        textDat_obj = macroCallbacksComp.create(textDAT, macro_uuid)
        textDat_obj.par.language = 'python'
        textDat_obj.text = output
        textDat_obj.save(callbacks_file_path)
        textDat_obj.par.file = callbacks_file_path
        textDat_obj.par.syncfile = True
        textDat_obj.tags.add('macroCallbacks')
    except Exception:
        print(f"Error creating callback DAT for {macro_uuid}: {traceback.format_exc()}")
