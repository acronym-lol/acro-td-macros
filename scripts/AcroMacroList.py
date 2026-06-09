from json import loads, dumps
from pprint import pprint
import traceback

from CallbacksExt import CallbacksExt
from TDStoreTools import StorageManager
TDF = op.TDModules.mod.TDFunctions

class AcroMacroList(CallbacksExt):
    """ A list to display and select Macros """

    def __init__(self, ownerComp):
        # the component to which this extension is attached
        self.ownerComp = ownerComp

        # init callbacks
        self.callbackDat = self.ownerComp.par.Callbackdat.eval()
        try:
            CallbacksExt.__init__(self, ownerComp)
        except:
            self.ownerComp.addScriptError(traceback.format_exc() + \
                    "Error in CallbacksExt __init__. See textport.")
            print()
            print("Error initializing callbacks - " + self.ownerComp.path)
            print(traceback.format_exc())
        # run onInit callback
        try:
            self.DoCallback('onInit', {'ownerComp':self.ownerComp})
        except:
            self.ownerComp.addScriptError(traceback.format_exc() + \
                    "Error in custom onInit callback. See textport.")
            print(traceback.format_exc())

        # the component to which data is stored
        self.dataComp = ownerComp.op('data')

        self.dragRow = False
        self.dropType = None
        self.endRow = None

        # stored items (persistent across saves and re-initialization):
        storedItems = [
            # Only 'name' is required...
            {'name': 'Data', 'default': [], 'readOnly': False,
                                     'property': True, 'dependable': True},
        ]
        self.stored = StorageManager(self, self.dataComp, storedItems)

        self.InitData()
        self.list = ownerComp.op('list')
        self.list.par.reset.pulse()

    # initialize list data
    def InitData(self):

        dataStructure = self.ownerComp.par.Datastructure.eval()
       
        data = []

        def buildData(dataStructure, data, level=0, path=[]):
            item_number = 0
            for item in dataStructure:
                data.append(
                    {
                        'level': level,
                        'path': path + [item_number],
                        'hasChildren': len(item['children']) > 0,
                    }
                )
                if len(item['children']) > 0 and item['expanded']:
                    buildData(item['children'], data, level + 1, path + [item_number])
                item_number += 1
        
        buildData(dataStructure, data)
        
        self.stored['Data'] = data


    # me - this DAT
    # 
    # comp - the List Component that holds this panel
    # row - the row number of the cell being updated
    # col - the column number of the cell being updated
    #
    # attribs contains the following members:
    #
    # text                 str            cell contents
    # help                 str            help text
    #
    # textColor            r g b a        font color
    # textOffsetX          n              horizontal text offset
    # textOffsetY          n              vertical text offset
    # textJustify          m              m is one of:  JustifyType.TOPLEFT, JustifyType.TOPCENTER,
    #                                                   JustifyType.TOPRIGHT, JustifyType.CENTERLEFT,
    #                                                   JustifyType.CENTER, JustifyType.CENTERRIGHT,
    #                                                   JustifyType.BOTTOMLEFT, JustifyType.BOTTOMCENTER,
    #                                                   JustifyType.BOTTOMRIGHT
    #
    # bgColor              r g b a        background color
    #
    # leftBorderInColor    r g b a         inside left border color
    # rightBorderInColor   r g b a         inside right border color
    # bottomBorderInColor  r g b a         inside bottom border color
    # topBorderInColor     r g b a         inside top border color
    #
    # leftBorderOutColor   r g b a         outside left border color
    # rightBorderOutColor  r g b a         outside right border color
    # bottomBorderOutColor r g b a         outside bottom border color
    # topBorderOutColor    r g b a         outside top border color
    #
    # colWidth             w              sets column width
    # colStetch            True/False     sets column stretchiness (width is min width)
    # rowHeight            h              sets row height
    # rowStetch            True/False     sets row stretchiness (height is min height)
    # rowIndent            w              offsets entire row by this amount
    #
    # editable             int            number of clicks to activate editing the cell.
    # draggable            True/False     allows cell to be drag/dropped elsewhere
    # fontBold             True/False     render font bolded
    # fontItalic           True/False     render font italicized
    # fontSizeX            float          font X size in pixels
    # fontSizeY            float          font Y size in pixels, if not specified, uses X size
    # sizeInPoints         True/False     If true specify font size in points, rather than pixels.
    # wordWrap             True/False     word wrap
    # top                  TOP            background TOP operator
    #
    # fontFace             str            font face, example 'Verdana'
    # fontFile             str            font file, when specified on disk or embedded in VFS.
    #                                     When fontFace and fontFile are both defined in the same attrib,
    #                                     fontFile takes precedence
    #
    # select   true when the cell/row/col is currently being selected by the mouse
    # rollover true when the mouse is currently over the cell/row/col
    # radio    true when the cell/row/col was last selected
    # focus    true when the cell/row/col is being edited
    #
    #

    # called when Reset parameter is pulsed, or on load
    
    def hsv_to_rgb(self, hsv):
        h, s, v = hsv
        h, s, v = h / 360.0, s / 100.0, v / 100.0
        i = int(h * 6)
        f = (h * 6) - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)
        i = i % 6
        if i == 0: return v, t, p
        if i == 1: return q, v, p
        if i == 2: return p, v, t
        if i == 3: return p, q, v
        if i == 4: return t, p, v
        if i == 5: return v, p, q

    # get structure from row
    def getStructure(self, row):
        try:
            dataStructure = self.ownerComp.par.Datastructure.eval()

            path = self.stored['Data'][row]['path']
            structure = dataStructure[path[0]]
            if len(path) > 1:
                for i in range(1, len(path)):
                    structure = structure['children'][path[i]]
            return structure
        except:
            return None

    # called when a list cell is being updated
    def onInitCell(self, comp, row, col, attribs):   
        structure = self.getStructure(row)
        if structure != None:
            level = self.stored['Data'][row]['level']
            if col == 0:
                attribs.bgColor = op.MC.pars('Macrolistbg*')
                attribs.rightBorderOutColor = op.MC.pars(f'Macrolisttextl{max(level-1, 0) % 8}*')
                attribs.topBorderOutColor = op.MC.pars('Macrolistbg*')
                attribs.bottomBorderOutColor = op.MC.pars('Macrolistbg*')
            if col == 1:
                #text = ''.join(['| ' for i in range(self.stored['Data'][row]['level'])])
                text = ''
                level = min(self.stored['Data'][row]['level'], 7)
                if level > 0:
                    #text += '| '
                     attribs.rightBorderOutColor = op.MC.pars('Macrolistbg*')
                if self.stored['Data'][row]['hasChildren']:
                    if structure['expanded']:
                        text += 'v'
                    else:
                        text += '>'
                else:
                    text += ' '
                attribs.text = text
                attribs.textJustify = JustifyType.CENTERRIGHT
                attribs.textOffsetX = -4
                attribs.bgColor = op.MC.pars('Macrolistbg*')
                attribs.topBorderOutColor = op.MC.pars('Macrolistbg*')
                attribs.bottomBorderOutColor = op.MC.pars('Macrolistbg*')
                #attribs.colWidth = row * 200
            if col == 2:
                attribs.text = structure['name']
                attribs.help = 'Click to select, drag to reorder, double click to rename'
                attribs.textJustify = JustifyType.CENTERLEFT
                attribs.textOffsetX = 4
                attribs.editable = 2
                #attribs.draggable = True
                # if attribs.rollover:
                #     bgColor += .1
                # if structure['selected']:
                #     bgColor += .1
            if col == 3:
                attribs.text = 'E'
                attribs.textColor = op.MC.pars('Macrolisterroroff*')


                if structure['error']:
                    attribs.textColor = op.MC.pars('Macrolisterroron*')
                # if attribs.rollover:
                #     bgColor += .1
                # if structure['selected']:
                #     bgColor += .1

            # attribs.bgColor = (bgColor, bgColor, bgColor, 1)
        return
    
    # called when a list row is being updated
    def onInitRow(self, comp, row, attribs):
        
        # set row indent based on level
        attribs.rowIndent = (14 * self.stored['Data'][row]['level'])

        # use level-based text colors (clamp to 0-7)
        level = min(self.stored['Data'][row]['level'], 7)
        attribs.textColor = op.MC.pars(f'Macrolisttextl{level}*')

        bgColor = op.MC.pars('Macrolistcelloff*')
        structure = self.getStructure(row)
        if structure != None:
            if structure['selected']:
                if attribs.rollover:
                    bgColor = op.MC.pars('Macrolistcellonroll*')
                else:
                    bgColor = op.MC.pars('Macrolistcellon*')
            elif attribs.rollover:
                bgColor = op.MC.pars('Macrolistcelloffroll*')
            attribs.bgColor = bgColor
        return
    
    # called when a list column is being updated
    def onInitCol(self, comp, col, attribs):
        attribs.bgColor = op.MC.pars('Macrolistrowbg*')
        if col == 0:
            attribs.colWidth = 0
            attribs.bgColor = op.MC.pars('Macrolistbg*')
        if col == 1:
            attribs.colWidth = 21
            attribs.rightBorderOutColor = op.MC.pars('Macrolistrowbg*')
            
        if col == 2:
            attribs.colStretch = True
            attribs.bottomBorderOutColor = op.MC.pars('Macrolistborderdark*')
            attribs.topBorderOutColor = op.MC.pars('Macrolistborderlight*')
            attribs.leftBorderOutColor = op.MC.pars('Macrolistborderlight*')
        if col == 3:
            attribs.colWidth = 20
            attribs.bottomBorderOutColor = op.MC.pars('Macrolistborderdark*')
            attribs.topBorderOutColor = op.MC.pars('Macrolistborderlight*')
            attribs.rightBorderOutColor = op.MC.pars('Macrolistborderdark*')
        return
    def onInitTable(self, comp, attribs):
        return

    # called during specific events
    #
    # coords - a named tuple containing the following members:
    #   x
    #   y
    #   u
    #   v

    # called when a list cell is rolled over
    def onRollover(self, comp, row, col, coords, prevRow, prevCol, prevCoords):
        # update current row
        if row != None and row >= 0:
            if row != prevRow:
                structure = self.getStructure(row)
                if structure != None:
                    rowAttribs = comp.rowAttribs[row]
                    if structure['selected']:
                        rowAttribs.bgColor = op.MC.pars('Macrolistcellonroll*')
                    else:
                        rowAttribs.bgColor = op.MC.pars('Macrolistcelloffroll*')

        # reset previous row
        if prevRow != None and prevRow >= 0:
            if row != prevRow:
                structure = self.getStructure(prevRow)
                if structure != None:
                    prevRowAttribs = comp.rowAttribs[prevRow]
                    if structure['selected']:
                        prevRowAttribs.bgColor = op.MC.pars('Macrolistcellon*')
                    else:
                        prevRowAttribs.bgColor = op.MC.pars('Macrolistcelloff*')

        return

    # called when and/or while a list cell is selected
    def onSelect(self, comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
        #print('select', startRow, startCol, startCoords, endRow, endCol, endCoords, start, end)
        structure = self.getStructure(startRow)

        defaultBGColor = op.MC.pars('Macrolistcelloff*')
        defaultTopBorderOutColor = op.MC.pars('Macrolistborderlight*')
        defaultBottomBorderOutColor = op.MC.pars('Macrolistborderdark*')
        
        # input_info = {
        #     'startRow': startRow,
        #     'endRow': endRow,
        #     'start': start,
        #     'end': end,
        #     'dragRow': self.dragRow,
        #     'self_endRow': self.endRow,
        # }
        # pprint(input_info)
        # expand/collapse button
        if startCol == 1 and start:    
            structure['expanded'] = not structure['expanded']
            #self.InitData()  
        
        elif startCol == -1 and start:
            if comp.panel.lselect:
                self.DoCallback('onSelect', {'uuid': ''})
        
        # select macro
        elif startCol == 2 and start:
            # left select - select macro
            if comp.panel.lselect:
                self.dragRow = True
                self.endRow = startRow
                if startRow == endRow:
                    structure['selected'] = not structure['selected']
                    #self.InitData()
                    self.DoCallback('onSelect', {'uuid': structure['uuid']})
            
            # right select - open pop menu
            elif comp.panel.rselect:
                op.TDResources.PopMenu.Open(
                    items=['Add', 'Copy', 'Cut', 'Paste', 'Delete'],
                    callback=self.onSelectRightClick,
                    callbackDetails=[startRow],
                    disabledItems=None,
                    dividersAfterItems=None,
                    checkedItems=None,
                    subMenuItems=None,
                    autoClose=None,
                    rolloverCallback=None,
                )

        # end drag
        # endRow >= 0 prevents double clicking for some reason
        elif startCol == 2 and end and endRow >= 0:
            if self.dragRow:
                self.dragRow = False

                if startRow != endRow:
                    
                    # call onMove callback
                    self.onMove(startRow, endRow, self.dropType)

                    # reset row colors to default
                    endRowAttribs = comp.rowAttribs[endRow]

                    endRowAttribs.bgColor = defaultBGColor
                    endRowAttribs.topBorderOutColor = defaultTopBorderOutColor
                    endRowAttribs.bottomBorderOutColor = defaultBottomBorderOutColor
        
        # while dragging
        elif startCol == 2 and not start and not end and startRow != endRow and endRow != None:
            if self.dragRow:
                dragRowAttribs = comp.rowAttribs[endRow]

                defaultBGColor = op.MC.pars('Macrolistcelloff*')
                defaultTopBorderOutColor = op.MC.pars('Macrolistborderlight*')
                defaultBottomBorderOutColor = op.MC.pars('Macrolistborderdark*')

                highlightColor = op.MC.pars('Macrolistdraghighlight*')
                
                # drag over top - insert above
                if endCoords.v > .75:
                    dragRowAttribs.topBorderOutColor = highlightColor
                    dragRowAttribs.bottomBorderOutColor = defaultBottomBorderOutColor
                    dragRowAttribs.bgColor = defaultBGColor
                    self.dropType = 'above'

                # drag over bottom - insert below
                elif endCoords.v < .25:
                    dragRowAttribs.bottomBorderOutColor = highlightColor
                    dragRowAttribs.topBorderOutColor = defaultTopBorderOutColor
                    dragRowAttribs.bgColor = defaultBGColor
                    self.dropType = 'below'

                # drag over middle - insert inside
                else:
                    dragRowAttribs.bgColor = highlightColor
                    dragRowAttribs.topBorderOutColor = defaultTopBorderOutColor
                    dragRowAttribs.bottomBorderOutColor = defaultBottomBorderOutColor
                    self.dropType = 'inside'

                # drag off row - reset row colors
                if self.endRow != endRow:
                    if self.endRow != None and self.endRow != startRow:
                        endRowAttribs = comp.rowAttribs[self.endRow]

                        endRowAttribs.bgColor = defaultBGColor
                        endRowAttribs.topBorderOutColor = defaultTopBorderOutColor
                        endRowAttribs.bottomBorderOutColor = defaultBottomBorderOutColor

                    self.endRow = endRow

        # select error button - clear error
        elif startCol == 3 and start:
            op.MC.ClearMacroErrors(structure['uuid'])

        return
    
    def onMove(self, from_row, to_row, move_type):

        # get paths
        from_path = self.stored['Data'][from_row]['path'].getRaw()
        to_path = self.stored['Data'][to_row]['path'].getRaw()

        # check for moving inside self. if from path is a subset of to path, return
        if from_path == to_path[:len(from_path)]:
            print('cannot move inside self')
            return

        # if drop_type == 'above':
        #     to_path = to_path
        # elif drop_type == 'below':
        #     # if we are dropping below a child of the same parent, we consider the shift to be one less as the current row is being removed
        #     if from_path[:-1] == to_path[:-1]:
        #         to_path = to_path[:-1] + [to_path[-1]]
        #     else:
        #         to_path = to_path[:-1] + [to_path[-1] + 1]
        # elif drop_type == 'inside':
        #     to_path = to_path + [0]

        self.DoCallback('onMove', {'from_path': from_path, 'to_path': to_path, 'move_type': move_type})


    def onRadio(self, comp, row, col, prevRow, prevCol):
        return

    def onFocus(self, comp, row, col, prevRow, prevCol):
        return

    def onEdit(self, comp, row, col, val):
        structure = self.getStructure(row)
        # get macro uuid
        macro_uuid = structure['uuid']
        op.MC.RenameMacroUUID(macro_uuid, val)
        return
    
    #return True if interested in this drop event, False otherwise
    def onHover(self, comp, row, col, coords, prevrow, prevcol, prevcoords, dragItems):
        #print('hover', row, coords, dragItems)
        return False

    def onDrop(self, comp, row, col, coords, prevrow, prevcol, prevcoords, dragItems):
        #print('drop', row, coords, dragItems)
        return False
    
    def onSelectRightClick(self, info):
        row = info['details'][0]
        selection = info['item']
        path = self.stored['Data'][row]['path'].getRaw()
        self.DoCallback('onPopMenuSelect', {'selection': selection, 'path': path})
        return

    # pulse parameter to open extension
    def pulse_Editextension(self):
        self.ownerComp.op('AcroMacroList').par.edit.pulse()
