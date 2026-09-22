import unittest
from unittest.mock import MagicMock
from macro_helpers import (
    normalize_path,
    update_sibling_order,
    find_path,
    select_macro_recursive,
    update_child_callbacks
)

# Dummy TextDAT to simulate a TouchDesigner text DAT.
class DummyTextDAT:
    def __init__(self):
        self.text = "dummy text"
        self.module = MagicMock()

    def eval(self):
        return "dummy_eval"

# Dummy operator to simulate the TouchDesigner environment.
class DummyOp:
    def __init__(self):
        self.par = MagicMock()
        # Use a DummyTextDAT for Callbackdat.
        self.par.Callbackdat = MagicMock(eval=lambda: DummyTextDAT())
        self.par.Logtofile = MagicMock(eval=lambda: False)
        self.path = "dummy_path"
        self.tags = []
    def op(self, name):
        return None
    def addScriptError(self, err):
        print("DummyOp.addScriptError:", err)

# Dummy StorageManager – we'll override it in tests.
class DummyStorage(dict):
    pass

class TestMacroHelpers(unittest.TestCase):
    def setUp(self):
        # Create a dummy op instance.
        self.dummy_op = DummyOp()
        # Instead of instantiating Macros (which uses StorageManager), we simulate
        # just the parts needed for testing helper functions.
        # Here, we create a dummy storage structure.
        self.storage = DummyStorage({
            'MacroStructure': [
                {'uuid': '1', 'name': 'macro1', 'children': []},
                {'uuid': '2', 'name': 'macro2', 'children': []}
            ],
            'MacroData': {
                '1': {'order': 0, 'uuid': '1', 'name': 'macro1'},
                '2': {'order': 0, 'uuid': '2', 'name': 'macro2'}
            }
        })

    def test_normalize_path(self):
        """Test that normalize_path returns a consistently formatted path."""
        self.assertEqual(normalize_path("C:\\test\\path\\"), "C:/test/path")
        self.assertEqual(normalize_path("/test/path/"), "test/path")
        self.assertEqual(normalize_path("  /mixed\\slashes/  "), "mixed/slashes")

    def test_update_sibling_order(self):
        """Test that update_sibling_order correctly updates sibling orders in MacroData."""
        siblings = [
            {'uuid': '1', 'name': 'macro1'},
            {'uuid': '2', 'name': 'macro2'}
        ]
        test_storage = {'MacroData': {'1': {'order': 0}, '2': {'order': 0}}}
        update_sibling_order(siblings, test_storage)
        self.assertEqual(test_storage['MacroData']['1']['order'], 0)
        self.assertEqual(test_storage['MacroData']['2']['order'], 1)

    def test_find_path(self):
        """Test that find_path returns the correct path for a given UUID."""
        structure = [
            {'uuid': '1', 'name': 'macro1', 'children': []},
            {'uuid': '2', 'name': 'macro2', 'children': []}
        ]
        path = find_path(structure, '2', [])
        self.assertEqual(path, "macro2")

    def test_select_macro_recursive(self):
        """Test that select_macro_recursive correctly marks the target as selected."""
        structure = [
            {'uuid': '1', 'name': 'macro1', 'selected': False, 'children': []},
            {'uuid': '2', 'name': 'macro2', 'selected': False, 'children': []}
        ]
        select_macro_recursive(structure, '2')
        self.assertFalse(structure[0]['selected'])
        self.assertTrue(structure[1]['selected'])

    def test_update_child_callbacks(self):
        """Test that update_child_callbacks updates callback DAT file paths recursively."""
        # Create a dummy callbacks component that simulates op() behavior.
        class DummyCallbacksComp:
            def __init__(self):
                self.dats = {}
            def op(self, uuid):
                return self.dats.get(uuid)
            def add_dat(self, uuid, dat):
                self.dats[uuid] = dat

        class DummyDat:
            def __init__(self):
                self.par = type('par', (), {})()
                self.par.file = ""
        dummy_callbacks = DummyCallbacksComp()
        # Create a simple macro structure with one child.
        structure = {
            'uuid': '1',
            'name': 'parent',
            'children': [
                {'uuid': '2', 'name': 'child', 'children': []}
            ]
        }
        # Add dummy DATs for the parent and its child.
        dummy_callbacks.add_dat('1', DummyDat())
        dummy_callbacks.add_dat('2', DummyDat())
        # Call update_child_callbacks with a new base folder.
        update_child_callbacks(structure, "new/base/parent", dummy_callbacks)
        # Expected: parent's DAT file should be "new/base/parent/callbacks.py"
        # and child's DAT file should be "new/base/parent/child/callbacks.py"
        parent_dat = dummy_callbacks.op('1')
        child_dat = dummy_callbacks.op('2')
        #self.assertEqual(parent_dat.par.file, "new/base/parent/callbacks.py")
        self.assertEqual(child_dat.par.file, "new/base/parent/child/callbacks.py")

# Explicitly create and run the test suite.
suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMacroHelpers)
runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)

ext.AcroMacros.InitData()

class TestMacrosBasicFunctionality(unittest.TestCase):
    def setUp(self):
        # Get the AcroMacros instance from the TD environment.
        self.am = ext.AcroMacros
        # Initialize data (clearing out any previous macros)
        self.am.InitData(deleteFolders=True)

    def test_add_macro(self):
        """Test that adding a macro increases the MacroStructure count."""
        initial_count = len(self.am.stored['MacroStructure'])
        # Create a new macro at the root ("/")
        self.am.CreateMacro("TestMacro", "/")
        # Since macros are stored as a list in MacroStructure, get the new count.
        new_count = len(self.am.stored['MacroStructure'])
        self.assertEqual(new_count, initial_count + 1,
                         "MacroStructure should contain one more macro after adding one.")

    def test_delete_macro(self):
        """Test that deleting a macro removes it from the MacroStructure."""
        # Create a macro to delete.
        self.am.CreateMacro("TestMacroDelete", "/")
        # Assume the macro is at the root; its name should be "TestMacroDelete" or a modified version.
        names = [m['name'] for m in self.am.stored['MacroStructure']]
        # We expect at least one macro whose name starts with "TestMacroDelete"
        self.assertTrue(any(name.startswith("TestMacroDelete") for name in names),
                        "A macro starting with 'TestMacroDelete' should exist after creation.")
        # Now, delete the macro. For testing, we call DeleteMacro with the macro's path.
        # Assuming the macro is at the root, its path is simply its name.
        macro_path = [name for name in names if name.startswith("TestMacroDelete")][0]
        self.am.DeleteMacro(macro_path)
        names_after = [m['name'] for m in self.am.stored['MacroStructure']]
        self.assertFalse(any(name.startswith("TestMacroDelete") for name in names_after),
                         "No macro starting with 'TestMacroDelete' should exist after deletion.")

    def test_move_macro(self):
        """Test moving a macro from one parent to another updates the MacroStructure correctly."""
        # Create two macros at the root.
        self.am.CreateMacro("Parent1", "/")
        self.am.CreateMacro("Parent2", "/")
        # Create a child macro under Parent1.
        self.am.CreateMacro("Child", "/Parent1")
        # Get the current macro structure.
        parent1 = next((m for m in self.am.stored['MacroStructure'] if m['name'] == "Parent1"), None)
        parent2 = next((m for m in self.am.stored['MacroStructure'] if m['name'] == "Parent2"), None)
        self.assertIsNotNone(parent1, "Parent1 should exist.")
        self.assertIsNotNone(parent2, "Parent2 should exist.")
        # Confirm Parent1 has one child.
        self.assertEqual(len(parent1.get('children', [])), 1, "Parent1 should have one child initially.")
        # Move the child from Parent1 to Parent2.
        # To move, we specify the path indices. For example, assume:
        # Parent1 is at index 0 in MacroStructure, its child is at index 0.
        # Parent2 is at index 1.
        self.am.MoveMacro([0, 0], [1], "under")
        # Verify that Parent1 now has zero children and Parent2 has one child.
        parent1 = next((m for m in self.am.stored['MacroStructure'] if m['name'] == "Parent1"), None)
        parent2 = next((m for m in self.am.stored['MacroStructure'] if m['name'] == "Parent2"), None)
        self.assertEqual(len(parent1.get('children', [])), 0, "Parent1 should have no children after moving.")
        self.assertEqual(len(parent2.get('children', [])), 1, "Parent2 should have one child after moving.")

# Run tests directly (without the __name__ guard, since ext.AcroMacros is available in TD)
suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMacrosBasicFunctionality)
runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)

run(ext.AcroMacros.InitData, delayFrames=2)
