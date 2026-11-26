using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame.EditorTools
{
    /// <summary>Temporary, non-destructive mesh variants for art-direction previews.</summary>
    public static class ArtDirectionMeshes
    {
        // Geometry stays in the source mesh's local coordinate system. Small disconnected
        // details use their own grid; normal buckets stop opposite sides of a thin part
        // from being merged even if it happens to touch a much larger component.
        const float GridDivisions = 7f;
        const float ThinAxisDivisions = 5f;
        const int ProtectedVertexCount = 18;
        const float PaletteSteps = 32f;

        /// <summary>
        /// Returns a new coarse, flat-shaded mesh; never changes source data or transforms.
        /// The caller owns the returned mesh and should destroy it after the preview.
        /// UV0, UV1 (gloss/metal in MeshBuilder), and all other present UV streams retain
        /// their original corner values. Vertex-color alpha retains its emissive meaning.
        /// </summary>
        public static Mesh LowPoly(Mesh source)
        {
            if (source == null) return null;
            if (!source.isReadable)
                throw new ArgumentException("ArtDirectionMeshes.LowPoly requires a readable source mesh.", nameof(source));

            var positions = source.vertices;
            int vertexCount = positions.Length;
            if (vertexCount == 0) return Clone(source);

            var sourceNormals = source.normals;
            var sourceTangents = source.tangents;
            var sourceColors = source.colors;
            bool hasNormals = sourceNormals.Length == vertexCount;
            bool hasTangents = sourceTangents.Length == vertexCount;
            bool hasColors = sourceColors.Length == vertexCount;
            var uvStreams = ReadUVs(source, vertexCount);

            int subMeshCount = source.subMeshCount;
            var indices = new int[subMeshCount][];
            var topologies = new MeshTopology[subMeshCount];
            var parents = new int[vertexCount];
            var representatives = new int[vertexCount];
            for (int i = 0; i < vertexCount; i++) parents[i] = i;

            float longest = Mathf.Max(source.bounds.size.x, Mathf.Max(source.bounds.size.y, source.bounds.size.z));
            float weldTolerance = Mathf.Max(0.000001f, Mathf.Min(0.00001f, longest * 0.000001f));
            var welded = new Dictionary<PositionKey, int>(vertexCount);
            for (int i = 0; i < vertexCount; i++)
            {
                var key = new PositionKey(positions[i], weldTolerance);
                if (welded.TryGetValue(key, out int first))
                {
                    representatives[i] = first;
                    Union(parents, i, first);
                }
                else
                {
                    representatives[i] = i;
                    welded.Add(key, i);
                }
            }

            var geometricNormals = new Vector3[vertexCount];
            for (int s = 0; s < subMeshCount; s++)
            {
                // GetIndices applies the submesh baseVertex by default.
                indices[s] = source.GetIndices(s);
                topologies[s] = source.GetTopology(s);
                if (topologies[s] != MeshTopology.Triangles) continue;
                var tris = indices[s];
                for (int t = 0; t + 2 < tris.Length; t += 3)
                {
                    int a = tris[t], b = tris[t + 1], c = tris[t + 2];
                    Union(parents, a, b);
                    Union(parents, a, c);
                    var n = Vector3.Cross(positions[b] - positions[a], positions[c] - positions[a]);
                    geometricNormals[representatives[a]] += n;
                    geometricNormals[representatives[b]] += n;
                    geometricNormals[representatives[c]] += n;
                }
            }

            var componentForVertex = new int[vertexCount];
            var components = new Dictionary<int, Component>();
            for (int i = 0; i < vertexCount; i++)
            {
                int root = Find(parents, i);
                componentForVertex[i] = root;
                if (representatives[i] != i) continue;
                if (!components.TryGetValue(root, out var component))
                {
                    component = new Component { bounds = new Bounds(positions[i], Vector3.zero) };
                    components.Add(root, component);
                }
                component.bounds.Encapsulate(positions[i]);
                component.uniqueVertices++;
            }

            var buckets = new Dictionary<ClusterKey, int>(vertexCount);
            var clusters = new List<Cluster>();
            var clusterForVertex = new int[vertexCount];
            for (int i = 0; i < vertexCount; i++)
            {
                if (representatives[i] != i) continue;
                int root = componentForVertex[i];
                var component = components[root];
                int clusterIndex;
                if (component.uniqueVertices <= ProtectedVertexCount)
                {
                    clusterIndex = clusters.Count;
                    clusters.Add(new Cluster { sum = positions[i], count = 1 });
                }
                else
                {
                    var size = component.bounds.size;
                    float baseStep = Mathf.Max(size.x, Mathf.Max(size.y, size.z)) / GridDivisions;
                    var step = new Vector3(
                        AxisStep(size.x, baseStep, weldTolerance),
                        AxisStep(size.y, baseStep, weldTolerance),
                        AxisStep(size.z, baseStep, weldTolerance));
                    var key = new ClusterKey(root, positions[i], geometricNormals[i].normalized,
                        component.bounds, step, weldTolerance);
                    if (buckets.TryGetValue(key, out clusterIndex))
                    {
                        var cluster = clusters[clusterIndex];
                        cluster.sum += positions[i];
                        cluster.count++;
                        clusters[clusterIndex] = cluster;
                    }
                    else
                    {
                        clusterIndex = clusters.Count;
                        buckets.Add(key, clusterIndex);
                        clusters.Add(new Cluster { sum = positions[i], count = 1 });
                    }
                }
                clusterForVertex[i] = clusterIndex;
            }

            var clusteredPositions = new Vector3[vertexCount];
            for (int i = 0; i < vertexCount; i++)
            {
                int clusterIndex = clusterForVertex[representatives[i]];
                clusterForVertex[i] = clusterIndex;
                var cluster = clusters[clusterIndex];
                clusteredPositions[i] = cluster.sum / cluster.count;
            }

            // A small component must never disappear. If clustering collapses all its
            // triangles, retain its source geometry and still give it flat face shading.
            for (int s = 0; s < subMeshCount; s++)
            {
                if (topologies[s] != MeshTopology.Triangles) continue;
                var tris = indices[s];
                for (int t = 0; t + 2 < tris.Length; t += 3)
                {
                    int a = tris[t], b = tris[t + 1], c = tris[t + 2];
                    if (HasArea(clusteredPositions[a], clusteredPositions[b], clusteredPositions[c]))
                        components[componentForVertex[a]].hasSurvivingTriangle = true;
                }
            }
            for (int i = 0; i < vertexCount; i++)
                if (!components[componentForVertex[i]].hasSurvivingTriangle)
                    clusteredPositions[i] = positions[i];

            var outputPositions = new List<Vector3>(vertexCount);
            var outputNormals = new List<Vector3>(vertexCount);
            var outputTangents = hasTangents ? new List<Vector4>(vertexCount) : null;
            var outputColors = hasColors ? new List<Color>(vertexCount) : null;
            var outputIndices = new List<int>[subMeshCount];
            bool linearColors = QualitySettings.activeColorSpace == ColorSpace.Linear;

            for (int s = 0; s < subMeshCount; s++)
            {
                var sourceIndices = indices[s];
                var targetIndices = outputIndices[s] = new List<int>(sourceIndices.Length);
                if (topologies[s] == MeshTopology.Triangles)
                {
                    for (int t = 0; t + 2 < sourceIndices.Length; t += 3)
                    {
                        int a = sourceIndices[t], b = sourceIndices[t + 1], c = sourceIndices[t + 2];
                        var p0 = clusteredPositions[a];
                        var p1 = clusteredPositions[b];
                        var p2 = clusteredPositions[c];
                        var cross = Vector3.Cross(p1 - p0, p2 - p0);
                        if (cross.sqrMagnitude <= 1e-20f) continue;
                        var normal = cross.normalized;
                        var color = hasColors
                            ? FaceColor((sourceColors[a] + sourceColors[b] + sourceColors[c]) / 3f, linearColors)
                            : Color.white;
                        AddVertex(a, p0, normal, color, targetIndices);
                        AddVertex(b, p1, normal, color, targetIndices);
                        AddVertex(c, p2, normal, color, targetIndices);
                    }
                }
                else
                {
                    // Lines, points, and quads remain at their original positions and
                    // keep their topology, normals, and colors.
                    for (int i = 0; i < sourceIndices.Length; i++)
                    {
                        int v = sourceIndices[i];
                        AddVertex(v, positions[v], hasNormals ? sourceNormals[v] : Vector3.up,
                            hasColors ? sourceColors[v] : Color.white, targetIndices);
                    }
                }
            }

            if (outputPositions.Count == 0) return Clone(source);
            var result = new Mesh
            {
                name = source.name + "_ArtDirection_LowPoly",
                indexFormat = source.indexFormat == IndexFormat.UInt32 || outputPositions.Count > 65535
                    ? IndexFormat.UInt32 : IndexFormat.UInt16
            };
            result.SetVertices(outputPositions);
            result.SetNormals(outputNormals);
            if (hasTangents) result.SetTangents(outputTangents);
            if (hasColors) result.SetColors(outputColors);
            foreach (var stream in uvStreams) stream.Write(result);
            result.subMeshCount = subMeshCount;
            for (int s = 0; s < subMeshCount; s++)
                result.SetIndices(outputIndices[s], topologies[s], s, false);
            // Cluster centroids are convex combinations of source points. Preserve the
            // exact source bounds, including any authored padding, for stable framing.
            result.bounds = source.bounds;
            return result;

            void AddVertex(int sourceIndex, Vector3 position, Vector3 normal, Color color, List<int> target)
            {
                target.Add(outputPositions.Count);
                outputPositions.Add(position);
                outputNormals.Add(normal);
                if (hasColors) outputColors.Add(color);
                if (hasTangents)
                {
                    var oldTangent = sourceTangents[sourceIndex];
                    var tangent = new Vector3(oldTangent.x, oldTangent.y, oldTangent.z);
                    tangent -= normal * Vector3.Dot(tangent, normal);
                    if (tangent.sqrMagnitude < 1e-12f)
                        tangent = Vector3.Cross(Mathf.Abs(normal.y) < 0.9f ? Vector3.up : Vector3.right, normal);
                    tangent.Normalize();
                    outputTangents.Add(new Vector4(tangent.x, tangent.y, tangent.z, oldTangent.w));
                }
                foreach (var stream in uvStreams) stream.output.Add(stream.source[sourceIndex]);
            }
        }

        /// <summary>
        /// Returns a toy-like rounded variant for static vehicle/prop meshes. One midpoint
        /// subdivision gives box faces enough geometry to round; two gentle smoothing passes
        /// preserve each connected part's size and center. Small/thin parts keep their shape.
        /// UVs and colors interpolate only within their original faces, preserving seams.
        /// </summary>
        public static Mesh Rounded(Mesh source)
        {
            if (source == null) return null;
            if (!source.isReadable)
                throw new ArgumentException("ArtDirectionMeshes.Rounded requires a readable source mesh.", nameof(source));
            if (source.vertexCount == 0)
            {
                var empty = UnityEngine.Object.Instantiate(source);
                empty.name = source.name + "_ArtDirection_Rounded";
                return empty;
            }

            int originalCount = source.vertexCount;
            var positions = new List<Vector3>(source.vertices);
            var colors = new List<Color>(source.colors);
            var tangents = new List<Vector4>(source.tangents);
            var sourceNormals = source.normals;
            bool hasColors = colors.Count == originalCount;
            bool hasTangents = tangents.Count == originalCount;
            var streams = ReadUVs(source, originalCount);
            var topology = new MeshTopology[source.subMeshCount];
            var triangles = new List<int>[source.subMeshCount];
            var midpoints = new Dictionary<ulong, int>();

            for (int s = 0; s < source.subMeshCount; s++)
            {
                topology[s] = source.GetTopology(s);
                var old = source.GetIndices(s);
                var next = triangles[s] = new List<int>(topology[s] == MeshTopology.Triangles ? old.Length * 4 : old.Length);
                if (topology[s] != MeshTopology.Triangles) { next.AddRange(old); continue; }
                for (int t = 0; t + 2 < old.Length; t += 3)
                {
                    int a = old[t], b = old[t + 1], c = old[t + 2];
                    int ab = Midpoint(a, b), bc = Midpoint(b, c), ca = Midpoint(c, a);
                    next.Add(a); next.Add(ab); next.Add(ca);
                    next.Add(ab); next.Add(b); next.Add(bc);
                    next.Add(ca); next.Add(bc); next.Add(c);
                    next.Add(ab); next.Add(bc); next.Add(ca);
                }
            }

            int count = positions.Count;
            var parents = new int[count];
            var representatives = new int[count];
            var welded = new Dictionary<PositionKey, int>(count);
            var neighbours = new Dictionary<int, HashSet<int>>();
            for (int i = 0; i < count; i++) parents[i] = i;
            for (int i = 0; i < count; i++)
            {
                var key = new PositionKey(positions[i], 0.00001f);
                if (welded.TryGetValue(key, out int first))
                {
                    representatives[i] = first;
                    Union(parents, i, first);
                }
                else
                {
                    representatives[i] = i;
                    welded.Add(key, i);
                    neighbours.Add(i, new HashSet<int>());
                }
            }
            for (int s = 0; s < triangles.Length; s++)
            {
                if (topology[s] != MeshTopology.Triangles) continue;
                var tris = triangles[s];
                for (int t = 0; t + 2 < tris.Count; t += 3)
                {
                    int a = representatives[tris[t]], b = representatives[tris[t + 1]], c = representatives[tris[t + 2]];
                    Union(parents, a, b); Union(parents, a, c);
                    Connect(a, b); Connect(b, c); Connect(c, a);
                }
            }

            var roots = new int[count];
            var bounds = new Dictionary<int, Bounds>();
            for (int i = 0; i < count; i++)
            {
                int root = roots[i] = Find(parents, i);
                if (bounds.TryGetValue(root, out var box)) box.Encapsulate(positions[i]);
                else box = new Bounds(positions[i], Vector3.zero);
                bounds[root] = box;
            }
            var roundable = new HashSet<int>();
            foreach (var entry in bounds)
            {
                var size = entry.Value.size;
                float longest = Mathf.Max(size.x, Mathf.Max(size.y, size.z));
                float shortest = Mathf.Min(size.x, Mathf.Min(size.y, size.z));
                // Preserve spikes, barrels, antennae, rails, flat panels, and tiny details.
                if (longest >= 0.55f && shortest >= 0.12f && shortest / longest >= 0.12f)
                    roundable.Add(entry.Key);
            }

            var relaxed = positions.ToArray();
            for (int pass = 0; pass < 2; pass++)
            {
                var next = (Vector3[])relaxed.Clone();
                foreach (var entry in neighbours)
                {
                    int v = entry.Key;
                    if (!roundable.Contains(roots[v]) || entry.Value.Count == 0) continue;
                    var average = Vector3.zero;
                    foreach (int adjacent in entry.Value) average += relaxed[adjacent];
                    next[v] = Vector3.Lerp(relaxed[v], average / entry.Value.Count, 0.5f);
                }
                for (int i = 0; i < count; i++) next[i] = next[representatives[i]];
                relaxed = next;
            }

            var relaxedBounds = new Dictionary<int, Bounds>();
            for (int i = 0; i < count; i++)
            {
                if (relaxedBounds.TryGetValue(roots[i], out var box)) box.Encapsulate(relaxed[i]);
                else box = new Bounds(relaxed[i], Vector3.zero);
                relaxedBounds[roots[i]] = box;
            }
            for (int i = 0; i < count; i++)
            {
                int root = roots[i];
                if (!roundable.Contains(root)) continue;
                var before = bounds[root];
                var after = relaxedBounds[root];
                var scale = new Vector3(before.size.x / Mathf.Max(after.size.x, 1e-6f),
                    before.size.y / Mathf.Max(after.size.y, 1e-6f), before.size.z / Mathf.Max(after.size.z, 1e-6f));
                relaxed[i] = before.center + Vector3.Scale(relaxed[i] - after.center, scale);
            }

            var normalSums = new Vector3[count];
            for (int s = 0; s < triangles.Length; s++)
            {
                if (topology[s] != MeshTopology.Triangles) continue;
                var tris = triangles[s];
                for (int t = 0; t + 2 < tris.Count; t += 3)
                {
                    int a = tris[t], b = tris[t + 1], c = tris[t + 2];
                    var normal = Vector3.Cross(relaxed[b] - relaxed[a], relaxed[c] - relaxed[a]);
                    normalSums[representatives[a]] += normal;
                    normalSums[representatives[b]] += normal;
                    normalSums[representatives[c]] += normal;
                }
            }
            var normals = new Vector3[count];
            for (int i = 0; i < count; i++)
            {
                var normal = normalSums[representatives[i]];
                normals[i] = normal.sqrMagnitude > 1e-20f ? normal.normalized
                    : (i < sourceNormals.Length ? sourceNormals[i] : Vector3.up);
                if (!hasTangents) continue;
                var old = tangents[i];
                var tangent = new Vector3(old.x, old.y, old.z);
                tangent -= normals[i] * Vector3.Dot(tangent, normals[i]);
                if (tangent.sqrMagnitude < 1e-12f)
                    tangent = Vector3.Cross(Mathf.Abs(normals[i].y) < 0.9f ? Vector3.up : Vector3.right, normals[i]);
                tangent.Normalize();
                tangents[i] = new Vector4(tangent.x, tangent.y, tangent.z, old.w);
            }

            var result = new Mesh
            {
                name = source.name + "_ArtDirection_Rounded",
                indexFormat = source.indexFormat == IndexFormat.UInt32 || count > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16
            };
            result.SetVertices(relaxed);
            result.SetNormals(normals);
            if (hasColors) result.SetColors(colors);
            if (hasTangents) result.SetTangents(tangents);
            foreach (var stream in streams)
            {
                stream.output.AddRange(stream.source);
                // MeshBuilder's UV3 stores smooth outline normals, rather than texture UVs.
                if (stream.channel == 3 && stream.dimensions >= 3)
                    for (int i = 0; i < count; i++)
                        stream.output[i] = new Vector4(normals[i].x, normals[i].y, normals[i].z, stream.output[i].w);
                stream.Write(result);
            }
            result.subMeshCount = triangles.Length;
            for (int s = 0; s < triangles.Length; s++) result.SetIndices(triangles[s], topology[s], s, false);
            result.bounds = source.bounds;
            return result;

            int Midpoint(int a, int b)
            {
                ulong key = ((ulong)(uint)Mathf.Min(a, b) << 32) | (uint)Mathf.Max(a, b);
                if (midpoints.TryGetValue(key, out int midpoint)) return midpoint;
                midpoint = positions.Count;
                midpoints.Add(key, midpoint);
                positions.Add((positions[a] + positions[b]) * 0.5f);
                if (hasColors) colors.Add((colors[a] + colors[b]) * 0.5f);
                if (hasTangents) tangents.Add((tangents[a] + tangents[b]) * 0.5f);
                foreach (var stream in streams) stream.source.Add((stream.source[a] + stream.source[b]) * 0.5f);
                return midpoint;
            }

            void Connect(int a, int b)
            {
                if (a == b) return;
                neighbours[a].Add(b);
                neighbours[b].Add(a);
            }
        }

        static Mesh Clone(Mesh source)
        {
            var clone = UnityEngine.Object.Instantiate(source);
            clone.name = source.name + "_ArtDirection_LowPoly";
            return clone;
        }

        static float AxisStep(float extent, float baseStep, float tolerance)
            => Mathf.Max(tolerance, Mathf.Min(baseStep, extent / ThinAxisDivisions));

        static bool HasArea(Vector3 a, Vector3 b, Vector3 c)
            => Vector3.Cross(b - a, c - a).sqrMagnitude > 1e-20f;

        static Color FaceColor(Color color, bool linear)
        {
            // Quantize perceptual color rather than crushing the dark linear-space
            // values of the black car. Alpha is data for the project's toon shader.
            float alpha = color.a;
            if (linear) color = color.gamma;
            color.r = Mathf.Round(color.r * PaletteSteps) / PaletteSteps;
            color.g = Mathf.Round(color.g * PaletteSteps) / PaletteSteps;
            color.b = Mathf.Round(color.b * PaletteSteps) / PaletteSteps;
            if (linear) color = color.linear;
            color.a = alpha;
            return color;
        }

        static List<UVStream> ReadUVs(Mesh mesh, int vertexCount)
        {
            var streams = new List<UVStream>(8);
            for (int channel = 0; channel < 8; channel++)
            {
                var attribute = (VertexAttribute)((int)VertexAttribute.TexCoord0 + channel);
                if (!mesh.HasVertexAttribute(attribute)) continue;
                var stream = new UVStream { channel = channel, dimensions = mesh.GetVertexAttributeDimension(attribute) };
                mesh.GetUVs(channel, stream.source);
                if (stream.source.Count == vertexCount) streams.Add(stream);
            }
            return streams;
        }

        static int Find(int[] parents, int i)
        {
            int root = i;
            while (parents[root] != root) root = parents[root];
            while (parents[i] != i)
            {
                int next = parents[i];
                parents[i] = root;
                i = next;
            }
            return root;
        }

        static void Union(int[] parents, int a, int b)
        {
            int x = Find(parents, a), y = Find(parents, b);
            if (x != y) parents[Mathf.Max(x, y)] = Mathf.Min(x, y);
        }

        sealed class Component
        {
            public Bounds bounds;
            public int uniqueVertices;
            public bool hasSurvivingTriangle;
        }

        struct Cluster
        {
            public Vector3 sum;
            public int count;
        }

        readonly struct PositionKey : IEquatable<PositionKey>
        {
            readonly int x, y, z;
            public PositionKey(Vector3 p, float tolerance)
            {
                x = Mathf.RoundToInt(p.x / tolerance);
                y = Mathf.RoundToInt(p.y / tolerance);
                z = Mathf.RoundToInt(p.z / tolerance);
            }
            public bool Equals(PositionKey other) => x == other.x && y == other.y && z == other.z;
            public override bool Equals(object obj) => obj is PositionKey other && Equals(other);
            public override int GetHashCode()
            {
                unchecked { return ((x * 397) ^ y) * 397 ^ z; }
            }
        }

        readonly struct ClusterKey : IEquatable<ClusterKey>
        {
            readonly int component, x, y, z, nx, ny, nz, boundary;
            public ClusterKey(int component, Vector3 p, Vector3 normal, Bounds bounds, Vector3 step, float tolerance)
            {
                this.component = component;
                var local = p - bounds.min;
                x = Mathf.FloorToInt(local.x / step.x);
                y = Mathf.FloorToInt(local.y / step.y);
                z = Mathf.FloorToInt(local.z / step.z);
                nx = Mathf.RoundToInt(normal.x * 1.25f);
                ny = Mathf.RoundToInt(normal.y * 1.25f);
                nz = Mathf.RoundToInt(normal.z * 1.25f);
                boundary = (Mathf.Abs(p.x - bounds.min.x) <= tolerance ? 1 : 0)
                    | (Mathf.Abs(p.x - bounds.max.x) <= tolerance ? 2 : 0)
                    | (Mathf.Abs(p.y - bounds.min.y) <= tolerance ? 4 : 0)
                    | (Mathf.Abs(p.y - bounds.max.y) <= tolerance ? 8 : 0)
                    | (Mathf.Abs(p.z - bounds.min.z) <= tolerance ? 16 : 0)
                    | (Mathf.Abs(p.z - bounds.max.z) <= tolerance ? 32 : 0);
            }
            public bool Equals(ClusterKey o) => component == o.component && x == o.x && y == o.y && z == o.z
                && nx == o.nx && ny == o.ny && nz == o.nz && boundary == o.boundary;
            public override bool Equals(object obj) => obj is ClusterKey other && Equals(other);
            public override int GetHashCode()
            {
                unchecked
                {
                    int hash = component;
                    hash = hash * 397 ^ x; hash = hash * 397 ^ y; hash = hash * 397 ^ z;
                    hash = hash * 397 ^ nx; hash = hash * 397 ^ ny; hash = hash * 397 ^ nz;
                    return hash * 397 ^ boundary;
                }
            }
        }

        sealed class UVStream
        {
            public int channel, dimensions;
            public readonly List<Vector4> source = new List<Vector4>();
            public readonly List<Vector4> output = new List<Vector4>();
            public void Write(Mesh mesh)
            {
                if (dimensions <= 2)
                {
                    var values = new List<Vector2>(output.Count);
                    foreach (var uv in output) values.Add(new Vector2(uv.x, uv.y));
                    mesh.SetUVs(channel, values);
                }
                else if (dimensions == 3)
                {
                    var values = new List<Vector3>(output.Count);
                    foreach (var uv in output) values.Add(new Vector3(uv.x, uv.y, uv.z));
                    mesh.SetUVs(channel, values);
                }
                else mesh.SetUVs(channel, output);
            }
        }
    }
}
