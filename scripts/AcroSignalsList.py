from json import loads, dumps
import traceback

from CallbacksExt import CallbacksExt
from TDStoreTools import StorageManager
TDF = op.TDModules.mod.TDFunctions

class AcroSignalsList(CallbacksExt):
    """ A widget to display signal routing in AcroMacros """

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

        # stored items (persistent across saves and re-initialization):
        storedItems = [
            # Only 'name' is required...
            {'name': 'Data', 'default': None, 'readOnly': False,
                                     'property': True, 'dependable': True},
        ]
        self.stored = StorageManager(self, self.dataComp, storedItems)
        self.InitData()

    # initialize list data
    def InitData(self):

        dataStructure = self.ownerComp.par.Datastructure.eval()
       
        data = []
        signals = []

        for signal in dataStructure.keys():
            signals.append(signal)

        signals.sort()
        
        for signal in signals:            
            data.append({
                'label': signal,
                'level': 0,
            })
            routes = dataStructure[signal].getRaw()
            routes.sort()
            for r in routes:
                data.append({
                    'label': r,
                    'level': 1,
                })
        
        self.stored['Data'] = data

    def getData(self, row):
        """ Get the data for a specific row """
        if self.stored['Data'] != None and row >= 0 and row < len(self.stored['Data']):
            return self.stored['Data'][row]
        return None
    
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

   # called when a list cell is being updated
    def onInitCell(self, comp, row, col, attribs):   
        data = self.getData(row)
        if data != None:
            if col == 1:
                label = data['label']
                if data['level'] == 0:
                    #label = '~ ' + label + ' ~'
                    label = label
                else:
                    label = '| ' + label
                attribs.text = label
                attribs.textJustify = JustifyType.CENTERLEFT
                attribs.textOffsetX = 4
                #attribs.draggable = True
                # if attribs.rollover:
                #     bgColor += .1
                # if structure['selected']:
                #     bgColor += .1

        return
    
    # called when a list row is being updated
    def onInitRow(self, comp, row, attribs):
        data = self.getData(row)
        # set row indent based on level
        attribs.rowIndent = 6 + (14 * data['level'])

        # add hue offset based on level
        attribs.textColor = self.hsv_to_rgb((120+data['level'] * -250 % 360, 40, 100)) + (1,)

        bgColor = .2

        if data != None:
            if attribs.rollover:
                bgColor += .1
            attribs.bgColor = (bgColor, bgColor, bgColor, 1)
        return
    
    # called when a list column is being updated
    def onInitCol(self, comp, col, attribs):
        attribs.bgColor = (0.15, 0.15, 0.15, 1)
        if col == 0:
            attribs.colStretch = False
            attribs.colWidth = 0
            attribs.bottomBorderOutColor = (0.1, 0.1, 0.1, 1)
            attribs.topBorderOutColor = (0.25, 0.25, 0.25, 1)
            attribs.leftBorderOutColor = (0.25, 0.25, 0.25, 1)
        elif col == 1:
            attribs.colStretch = True
            attribs.bottomBorderOutColor = (0.1, 0.1, 0.1, 1)
            attribs.topBorderOutColor = (0.25, 0.25, 0.25, 1)
            #attribs.leftBorderOutColor = (0.25, 0.25, 0.25, 1)
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
        #print('rollover', row, col, coords)
        
        
        if row != None and row >= 0:
            if row != prevRow:
                bgColor = .2
                structure = self.getData(row)
                if structure != None:
                    rowAttribs = comp.rowAttribs[row]
                    bgColor += .1

                    rowAttribs.bgColor = (bgColor, bgColor, bgColor, 1)

        if prevRow != None and prevRow >= 0:
            if row != prevRow:
                bgColor = .2
                structure = self.getData(prevRow)
                if structure != None:
                    prevRowAttribs = comp.rowAttribs[prevRow]
                    prevRowAttribs.bgColor = (bgColor, bgColor, bgColor, 1)

                    

        return

    # called when and/or while a list cell is selected
    def onSelect(self, comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
        #print('select', startRow, startCol, startCoords, endRow, endCol, endCoords, start, end)

        defaultBGColor = (0.2, 0.2, 0.2, 1)
        defaultTopBorderOutColor = (0.25, 0.25, 0.25, 1)
        defaultBottomBorderOutColor = (0.1, 0.1, 0.1, 1)
        
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
        if startCol == 0 and start:    
            pass

        return
    



    def onRadio(self, comp, row, col, prevRow, prevCol):
        return

    def onFocus(self, comp, row, col, prevRow, prevCol):
        return

    def onEdit(self, comp, row, col, val):
        return
    
    #return True if interested in this drop event, False otherwise
    def onHover(self, comp, row, col, coords, prevrow, prevcol, prevcoords, dragItems):
        #print('hover', row, coords, dragItems)
        return False

    def onDrop(self, comp, row, col, coords, prevrow, prevcol, prevcoords, dragItems):
        #print('drop', row, coords, dragItems)
        return False
    
    def onSelectRightClick(self, info):
        #print('right click', info)
        return

    def onCloseRightClick(self, info):
        #print('closed', info)
        return

    # pulse parameter to open extension
    def pulse_Editextension(self):
        self.ownerComp.op('AcroSignalsList').par.edit.pulse()
