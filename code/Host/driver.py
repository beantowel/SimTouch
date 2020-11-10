import time
import subprocess
import numbers
import numpy as np
from itertools import product
import matplotlib.pyplot as plt

# SET <buffer data>*2 <duty>*2
# TOUCH <duration>
# SLEEP <duration>
# DRAW <new duty>*2 <duration>
MACRO = {
    'SET': 0xFF,
    'TOUCH': 0xFE,
    'SLEEP': 0xFD,
    'DRAW': 0xFC,
}
MAXT = 0x10000
MINT = 0
COLS = 8
ROWS = 8
TCH_BUF_SIZE = (COLS + ROWS) // 8
USB_FS_MAX_PACKET_SIZE = 64
RX_RING_SIZE = 16
MACRO_LEN = {
    MACRO['SET']: 1 + TCH_BUF_SIZE * 2 + 2,
    MACRO['TOUCH']: 1 + 2,
    MACRO['SLEEP']: 1 + 2,
    MACRO['DRAW']: 1 + 2 + 2,
}
SERIAL_ID = 'usb-STMicroelectronics_STM32_Virtual_ComPort_6D8214965455-if00'


def splitData(data, size=USB_FS_MAX_PACKET_SIZE):
    i, commands = 0, []
    while(i < len(data)):
        l = MACRO_LEN[data[i]]
        commands.append(data[i:i+l])
        i += l
    commandLens = list(map(len, commands))

    accuLen, sdata = 0, []
    for command, l in zip(commands, commandLens):
        if accuLen + l <= USB_FS_MAX_PACKET_SIZE:
            accuLen += l
            sdata += command
        else:
            yield sdata
            accuLen, sdata = l, command
    yield sdata


def transferSerial(data, sid=SERIAL_ID):
    '''send data through serial by id'''
    print(f'send via VCP')
    spld = list(splitData(data))
    assert len(spld) < RX_RING_SIZE, f'{len(spld)} exceeds {RX_RING_SIZE}'
    for sdata in spld:
        print(f'data[{len(sdata)}]:{sdata}')
        hexStr = ''.join([f'\\x{i:02X}' for i in sdata])
        command = ('echo', '-e', '-n', hexStr)
        command2 = ('sudo', 'tee', '-a', f'/dev/serial/by-id/{sid}')
        ps = subprocess.Popen(command, stdout=subprocess.PIPE)
        _ = subprocess.check_output(command2, stdin=ps.stdout)
        ps.wait()
        # print(f'echo hexStr:{hexStr}')


def splitBytes(x, len):
    '''split x into <len> LSB bytes'''
    data = []
    for i in range(len):
        a = x % 0x100
        x = x // 0x100
        data.append(a)
    return data


def duration(t):
    assert isinstance(t, numbers.Integral), f'{type(t)}'
    assert t < MAXT, f'{t}ms exceeds {MAXT}ms'
    return splitBytes(t, 2)


def sleep(t):
    '''sleep <t> in milliseconds'''
    data = [MACRO['SLEEP']] + duration(t)
    return data


def touch(t):
    '''make a touch with duration <t>'''
    data = [MACRO['TOUCH']] + duration(t)
    return data


def getBuffer(xList, yList):
    '''x, y list of addr selection'''
    Mod = 0x100
    x = sum([1 << i for i in xList])
    y = sum([1 << i for i in yList])
    X, Y = [], []
    for i in range(COLS // 8):
        X.append(x % Mod)
        x = x // Mod
    for i in range(ROWS // 8):
        Y.append(y % Mod)
        y = y // Mod
    data = X + Y
    return data


def segment(a, MAX, lower=True):
    '''super resolution segmentation
    input: <float>a <int>MAX,
    return: HiList, LoList, duty

    Lo + (Hi - Lo) * duty = A
    A ∈ [0, MAX-1]
    lower=True case:
    Lo <= A < Hi, (Hi - Lo) == 1
    lower=False case:
    Lo < A <= Hi, (Hi - Lo) == 1'''
    assert 0 <= a and a + 1 <= MAX, f'{a} ∉ [0, {MAX - 1}]'
    equiPos = [i/2 for i in range(MAX*2-1)]  # [0, 0.5, 1, 1.5, ... , MAX-1]
    equiList = [[i//2] if i % 2 == 0 else [i//2, i//2 + 1]
                for i in range(MAX*2-1)]  # [[0], [0,1], [1], ... , [MAX-1]]

    if a == MAX - 1:
        return equiList[-1], equiList[-2], 1.
    elif a == 0:
        return equiList[1], equiList[0], 0.
    else:
        # a ∈ [0, MAX-1)
        for pos, lis, sucPos, sucLis in zip(
                equiPos[:-1], equiList[:-1], equiPos[1:], equiList[1:]):
            if (lower and pos <= a and a < sucPos) or ((not lower) and pos < a and a <= sucPos):
                duty = (a - pos) / (sucPos - pos)
                return sucLis, lis, duty
    raise ValueError


def setBoard(x, y, lowers=(True, True)):
    '''x,y ∈ [0, (COLS-1)|(ROWS-1)]'''
    assert 0 <= x and 0 <= y and x + 1 <= COLS and y + \
        1 <= ROWS, f'{x, y} out of range'
    xHi, xLo, col_duty = segment(x, COLS, lower=lowers[0])
    yHi, yLo, row_duty = segment(y, ROWS, lower=lowers[1])
    buffer = getBuffer(xHi, yHi)[:: -1] + getBuffer(xLo, yLo)[:: -1]
    duty = [int(col_duty * 0xFF), int(row_duty * 0xFF)]
    data = [MACRO['SET']] + buffer + duty
    return data


def drawAdjoin(A, B, t, stop=False):
    '''draw from point A(x,y) to point B(x,y) with duration <t> '''
    def testActivition(lowers):
        sgAx = segment(A[0], COLS, lower=lowers[0])[:-1]
        sgAy = segment(A[1], ROWS, lower=lowers[1])[:-1]
        sgBx = segment(B[0], COLS, lower=lowers[2])[:-1]
        sgBy = segment(B[1], ROWS, lower=lowers[3])[:-1]
        return sgAx == sgBx and sgAy == sgBy

    lowersList = list(product([True, False], repeat=4))
    tests = [testActivition(lowers) for lowers in lowersList]
    lowers = lowersList[tests.index(True)]

    setAData = setBoard(A[0], A[1], lowers=lowers[:2])
    setBData = setBoard(B[0], B[1], lowers=lowers[2:])
    assert setAData[:-2] == setBData[:-2], f'{setAData}, {setBData}'
    data = setAData + [MACRO['DRAW']] + setBData[-2:] + duration(t)
    data += touch(0) if stop else []
    return data


def setBoardRaw(xList, yList):
    data = [MACRO['SET']] + getBuffer(xList, yList)[:: -1]*2 + [0xFF, 0xFF]
    return data


def draw(points, tList, stop=False, plot=False):
    ''' assign <points> into segments:
    [0, 0.5, 1, 1.5, ... , MAX-1].
    Adjoin points in <drawRaw> command should be in the same segments,
    so interpolate (A, B)-(B', C)-...-(U', V)
    '''
    assert len(points) == len(tList)+1, f'{len(points)} != {len(tList)+1}'
    xBorder = np.array([i/2 for i in range(COLS*2-1)])
    yBorder = np.array([i/2 for i in range(ROWS*2-1)])
    iPoints = [(points[0][0], points[0][1])]  # interpolated points
    tInter = []  # interpolated durations
    for p1, p2, t in zip(points[:-1], points[1:], tList):
        # (y-y2)/(y1-y2) = (x-x2)/(x1-x2) two-points equation for a straight line
        # y = y2 + (y1-y2)*(x-x2)/(x1-x2)
        # x = x2 + (x1-x2)*(y-y2)/(y1-y2)
        x1, y1 = p1
        x2, y2 = p2
        # interpolate corrdinates in (y1, y2), (x1, x2)
        yInter = yBorder[(yBorder < max(y1, y2)) & (yBorder > min(y1, y2))]
        xInter = xBorder[(xBorder < max(x1, x2)) & (xBorder > min(x1, x2))]
        if not(x1 == x2 or y1 == y2):
            # merge for non-vertical or non-horizontal line
            y2x = x2 + (x1 - x2) * (yInter - y2) / (y1 - y2)
            x2y = y2 + (y1 - y2) * (xInter - x2) / (x1 - x2)
            xInter = np.concatenate((xInter, y2x))
            yInter = np.concatenate((yInter, x2y))
        xInter.sort()
        yInter.sort()
        # tune interpolate coordinates direction
        ys = yInter if y1 < y2 else yInter[::-1]
        xs = xInter if x1 < x2 else xInter[::-1]
        # add heads and tail
        ys = np.concatenate(([y1], ys, [y2])).round(decimals=3)
        xs = np.concatenate(([x1], xs, [x2])).round(decimals=3)
        # spread duration evenly by displacement
        d = np.sqrt((np.diff(xs)**2 + np.diff(ys)**2))
        ts = (t * d / np.sum(d)).astype(int)

        if x1 == x2:
            iPoints.extend([(x1, y) for y in ys[1:]])
        elif y1 == y2:
            iPoints.extend([(x, y1) for x in xs[1:]])
        else:
            iPoints.extend([(x, y) for x, y in zip(xs[1:], ys[1:])])
        tInter.extend(list(ts))

    if plot:
        plt.plot(np.array(iPoints).T[0], np.array(iPoints).T[1], 'o-')
        plt.show()

    data = []
    assert len(iPoints) == len(tInter)+1, f'{len(iPoints)} != {len(tInter)+1}'
    for p1, p2, t in zip(iPoints[:-1], iPoints[1:], tInter):
        if t >= MINT:
            dDraw = drawAdjoin(p1, p2, t)
            print(f'{p1}->{p2} in {t}ms')
            data += dDraw
    data += touch(0) if stop else []
    return data


def drawAtGrid(points, tList, stop=False, plot=False):
    '''hop draw on nearest grid intersections'''
    def cast2Grid(p):
        x, y = p
        x = xBorder[np.argmin(np.abs(xBorder - x))]
        y = yBorder[np.argmin(np.abs(yBorder - y))]
        return (x, y)

    assert len(points) == len(tList)+1, f'{len(points)} != {len(tList)+1}'
    xBorder = np.array([i/2 for i in range(COLS*2-1)])
    yBorder = np.array([i/2 for i in range(ROWS*2-1)])
    iPoints = list(map(cast2Grid, points))

    if plot:
        plt.plot(np.array(iPoints).T[0], np.array(iPoints).T[1], 'o-')
        plt.show()

    data = []
    assert len(iPoints) == len(tList)+1, f'{len(iPoints)} != {len(tList)+1}'
    for p1, p2, t in zip(iPoints[:-1], iPoints[1:], tList):
        print(f'{p1}->{p2} in {t}ms')
        setd = setBoard(p1[0], p1[1])
        data += setd + [MACRO['DRAW']] + setd[-2:] + duration(t)
    data += touch(0) if stop else []
    return data


# test
if __name__ == '__main__':
    while True:
        for i in range(8):
            for j in range(8):
                print(f'i, j:{i,j}')
                # <TEST TOUCH >
                data = setBoardRaw([i], [j]) + touch(50)

                # <TEST SUPERRESOLUTION TOUCH>
                # data = []
                # if i < 7 and j < 8:
                #     di = 0 if j % 2 == 0 else 0.2
                #     dj = 0
                #     data += setBoard(i+di, j+dj) + touch(200)
                # else:
                #     data = sleep(200)

                # <TEST BASIC DRAW>
                # if i < 7:
                #     data = drawRaw((i, j), (i + 0.49, j), 100) + \
                #         drawRaw((i + 0.5, j), (i + 0.9, j), 100, stop=True)
                # else:
                #     data = sleep(200)

                # <TEST SLEEP>
                # T = 23
                # dt = 300
                # data = sleep(dt) * (T - 1)

                # TEST MULTI-DRAW
                # T = 40
                # dt = 200
                # points = np.array([(np.cos(t/10), np.sin(t/10))
                #                    for t in range(T)])*3.5 + 3.5
                # points = np.abs(points)
                # points = np.array([(t/(T-1), 6/7) for t in range(T)]) * 7
                # ts = [dt]*(T - 1)
                # data = draw(points, ts, stop=True, plot=False)
                # data = drawAtGrid(points, ts, stop=True, plot=False)

                # # send data
                output = transferSerial(data)
                print('sent!')
                # time.sleep(dt / 1000 * (T - 1))
                time.sleep(.2)
