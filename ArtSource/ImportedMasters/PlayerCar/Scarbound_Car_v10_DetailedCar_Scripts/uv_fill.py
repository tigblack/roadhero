def fill(objs):
    uv_area = 0.0
    for o in objs:
        uvl = o.data.uv_layers["UVMap"].data
        for p in o.data.polygons:
            pts = [uvl[li].uv for li in p.loop_indices]
            a = 0.0
            for k in range(len(pts)):
                x0, y0 = pts[k]; x1, y1 = pts[(k + 1) % len(pts)]
                a += x0 * y1 - x1 * y0
            uv_area += abs(a) / 2
    return round(uv_area, 3)


def bounds(objs):
    us, vs = [], []
    for o in objs:
        for d in o.data.uv_layers["UVMap"].data:
            us.append(d.uv.x); vs.append(d.uv.y)
    return round(min(us), 3), round(max(us), 3), round(min(vs), 3), round(max(vs), 3)
