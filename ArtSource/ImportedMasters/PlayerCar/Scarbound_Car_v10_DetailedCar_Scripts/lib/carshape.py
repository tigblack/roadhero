"""Python port of RoadGame's ModelsCar.cs shape functions (Unity space: x right, y up, z forward).
Blender body space = (x, z_unity, y_unity). Use U2B / B2U to convert."""
import math

CarFrontAxleZ, CarRearAxleZ = 1.45, -1.42
CarFrontWheelR, CarRearWheelR = 0.38, 0.44
CarFrontWheelW, CarRearWheelW = 0.31, 0.45
CarFrontTrack, CarRearTrack = 0.86, 0.97
BedFrontZ, BedRearZ, BedFloorY, BedRailY, BedInnerX = -0.70, -2.17, 0.60, 0.99, 0.70
HarpoonMount = (0.0, BedFloorY, -1.55)
CarZFront, CarZRear = 2.37, -2.38
StripeIn, StripeOut = 0.3, 0.44
BodyShoulderR = 0.12
RoofFrontZ = 0.12


def clamp01(v):
    return max(0.0, min(1.0, v))


def lerp(a, b, t):
    return a + (b - a) * t


def U2B(p):
    return (p[0], p[2], p[1])


def B2U(p):
    return (p[0], p[2], p[1])


def CarT(z):
    return (z - (CarZFront + CarZRear) * 0.5) / ((CarZFront - CarZRear) * 0.5)


def Flare(z, axle, half):
    d = abs(z - axle) / half
    if d >= 1.0:
        return 0.0
    k = 1.0 - d * d
    return k * k


def CarHalfWidth(z):
    t = CarT(z)
    a = min(abs(t), 0.999)
    w = 0.86 * (1 - a ** 8) ** 0.12 if t >= 0 else 0.86 * (1 - a ** 16) ** 0.1
    return w + 0.075 * Flare(z, CarFrontAxleZ, 0.7) + 0.19 * Flare(z, CarRearAxleZ, 0.82)


def CarTop(z):
    if z > 0.55:
        u = (z - 0.55) / (CarZFront - 0.55)
        top = lerp(0.99, 0.87, u)
        if z > 2.05:
            top -= (z - 2.05) * (z - 2.05) * 1.2
        return top
    t2 = BedRailY
    if z < -2.28:
        t2 -= (-2.28 - z) * (-2.28 - z) * 3.0
    return t2


def CarBottom(z):
    y = 0.3
    if z > 2.0:
        y += (z - 2.0) * 0.55
    if z < -2.05:
        y += (-2.05 - z) * 0.5
    return y


def CarCrown(z):
    return 0.05 if z > 0.55 else 0.01


def SideX(w, s):
    return w * (0.92 + 0.08 * math.sin(math.pi * (0.12 + 0.72 * s)))


def BodyTopEdge(z):
    return SideX(CarHalfWidth(z), 1.0) - BodyShoulderR


def BedInnerHalf(z):
    return min(BedInnerX, BodyTopEdge(z) - 0.06)


def CarArchCut(z, yBot):
    wellX = 0.6
    best = yBot
    for i in range(2):
        zw = CarFrontAxleZ if i == 0 else CarRearAxleZ
        r = CarFrontWheelR if i == 0 else CarRearWheelR
        ra = r + 0.07
        d = z - zw
        if abs(d) >= ra:
            continue
        if i == 1:
            wellX = CarRearTrack - CarRearWheelW * 0.5 - 0.025
        y = r + math.sqrt(ra * ra - d * d)
        if y > best:
            best = y
    return best, wellX


def CabinRoofY(z):
    if z > RoofFrontZ:
        return lerp(1.31, 0.99, clamp01((z - RoofFrontZ) / (0.6 - RoofFrontZ)) ** 0.95)
    if z > -0.5:
        return 1.31 + 0.008 * math.sin((z + 0.5) / (RoofFrontZ + 0.5) * math.pi)
    u = clamp01((-0.5 - z) / (-0.5 - BedFrontZ))
    return 1.31 - 0.045 * u * u


def TopY(x, z):
    """Body deck height with crown at (x, z) (section formula)."""
    w = CarHalfWidth(z)
    xt = SideX(w, 1.0) - BodyShoulderR
    u = clamp01(abs(x) / xt) if xt > 0.01 else 0.0
    return CarTop(z) + CarCrown(z) * (1 - u * u)


def HoodY(x, z):
    u = clamp01(abs(x) / 0.72)
    return CarTop(z) + CarCrown(z) * (1 - u * u)


GunX, GunZ = 0.56, 1.05
GunMountY = HoodY(GunX, GunZ) + 0.025
