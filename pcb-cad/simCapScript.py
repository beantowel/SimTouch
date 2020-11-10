import sys
from pcbnew import *

pcb = GetBoard()
layertable = {}
for i in range(100):
    name = pcb.GetLayerName(i)
    if name == 'BAD INDEX!':
        break
    else:
        layertable[name] = i
 
ROWS = 8
COLS = 8
GAP = 8

# touch pads
RefNm = [f'H{1+i}' for i in range(COLS*ROWS)]
RefX = [GAP*(i//ROWS) for i in range(COLS*ROWS)]
RefY = [GAP*(i%ROWS) for i in range(COLS*ROWS)]
for Idx, Rn in enumerate(RefNm):
    nPart = pcb.FindModuleByReference(Rn)
    if nPart.IsFlipped():
        nPart.SetPosition(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    else:
        nPart.Flip(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    
## diodes
RefNm = [f'D{1+i}' for i in range(COLS*ROWS)]
RefX = [1.8+GAP*(i//ROWS) for i in range(COLS*ROWS)]
RefY = [-1.8+GAP*(i%ROWS) for i in range(COLS*ROWS)]
for Idx, Rn in enumerate(RefNm):
    nPart = pcb.FindModuleByReference(Rn)
    nPart.SetPosition(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    nPart.SetOrientationDegrees(0)

# resistors
RefNm = [f'R{1+i}' for i in range(COLS)]
RefX = [2.15++GAP*i for i in range(COLS)]
RefY = [57.15 for i in range(COLS)]
for Idx, Rn in enumerate(RefNm):
    nPart = pcb.FindModuleByReference(Rn)
    nPart.SetPosition(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    nPart.SetOrientationDegrees(180)


# leds
# axis X
RefNm = [f'D{65+i}' for i in range(COLS)] + [f'R{9+i}' for i in range(COLS)]
RefX = [-1.8+GAP*i for i in range(COLS)] + [-1.85+GAP*i for i in range(COLS)]
RefY = [57.15 for i in range(COLS)] + [53.3 for i in range(COLS)]
for Idx, Rn in enumerate(RefNm):
    nPart = pcb.FindModuleByReference(Rn)
    nPart.SetPosition(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    nPart.SetOrientationDegrees(180 if Idx < COLS else 0)

# axis Y
RefNm = [f'D{73+i}' for i in range(ROWS)] + [f'R{17+i}' for i in range(ROWS)]
RefX = [66.6 for i in range(ROWS)] + [62 for i in range(ROWS)]
RefY = [0+GAP*i for i in range(ROWS)] + [0+GAP*i for i in range(ROWS)]
for Idx, Rn in enumerate(RefNm):
    nPart = pcb.FindModuleByReference(Rn)
    nPart.SetPosition(wxPoint(FromMM(RefX[Idx]), FromMM(RefY[Idx])))
    nPart.SetOrientationDegrees(90)

Refresh()


