// Clean stylized 3D lighting for URP (mobile friendly). The shader keeps its historic name "RoadGame/Toon" so
// existing tools keep finding the game materials, but it is no longer a cel shader:
// - Soft wrapped diffuse with a gentle S-curve (no hard light bands), soft received shadows.
// - Shadowed side is tinted by the zone's shade color times a hemisphere fill (cool sky above, warm bounce below),
//   so shadows read as soft painted color, not as black.
// - Per-vertex material params in UV1: x = gloss, y = metal. They choose the highlight character:
//   matte (stone, cloth) = no highlight, rubber = very broad faint sheen, paint = broad soft cream highlight
//   plus a little clear-coat sky, glass = tighter highlight + sky, metal = albedo tinted highlight + tinted sky.
// - Broad painted dust gradient near the ground and soft ground-contact occlusion. No noise / grime textures,
//   no outlines, no hatching.
// - Vertex color alpha < 1 marks self-lit parts (lamps, glowing goo, crystals).
// - Occluder fade: a per-renderer copy of a material switches the blend state (_SrcBlend / _DstBlend / _ZWrite) and
//   lowers _Alpha, so roofs and lids turn see-through without touching the shared material (OcclusionFader).
Shader "RoadGame/Toon"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (1,1,1,1)
        _BaseMap ("Base Map", 2D) = "white" {}
        _VertexColorWeight ("Vertex RGB Weight (alpha always retained)", Range(0,1)) = 1
        [Toggle(_BAKED_MAPS)] _UseBakedMaps ("Use Baked Surface Maps", Float) = 0
        [Normal] _BumpMap ("Normal Map", 2D) = "bump" {}
        _BumpScale ("Normal Strength", Range(0,2)) = 1
        _MetallicGlossMap ("Metallic (R), Smoothness (A)", 2D) = "white" {}
        _OcclusionMap ("Baked Ambient Occlusion", 2D) = "white" {}
        _OcclusionStrength ("Baked Occlusion Strength", Range(0,1)) = 1
        _ShadeColor ("Shade Tint (zone)", Color) = (0.66,0.62,0.82,1)
        _TermLo ("Terminator start (N.L)", Range(-1,0.5)) = -0.5
        _TermHi ("Terminator end (N.L)", Range(0,1)) = 0.7
        _SpecStrength ("Highlight Strength", Range(0,2)) = 1
        _ReflStrength ("Sky Reflection Strength", Range(0,2)) = 1
        _GlossMul ("Vertex Gloss Multiplier", Range(0,2)) = 1
        _RimColor ("Rim Color (a = strength)", Color) = (1,0.96,0.88,0.12)
        _Emission ("Emission", Color) = (0,0,0,0)
        _WorldUV ("World UV scale (0 = mesh uv)", Float) = 0
        _FlashColor ("Flash Color (a = amount)", Color) = (1,1,1,0)
        _ShadowStrength ("Received Shadow Strength", Range(0,1)) = 1
        _DustAmount ("Ground Dust Gradient", Range(0,1)) = 0
        _AOFloor ("Ground Contact Occlusion (1 = none)", Range(0,1)) = 1
        _AOHeight ("Ground Contact Height (m)", Float) = 0.7
        _Saturation ("Albedo Saturation", Range(0,2)) = 1
        _Alpha ("Alpha (occluder fade)", Range(0,1)) = 1
        [HideInInspector] _SrcBlend ("__src", Float) = 1
        [HideInInspector] _DstBlend ("__dst", Float) = 0
        [HideInInspector] _ZWrite ("__zw", Float) = 1
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseColor;
            float4 _BaseMap_ST;
            float _VertexColorWeight;
            float _UseBakedMaps;
            float _BumpScale;
            float _OcclusionStrength;
            float4 _ShadeColor;
            float _TermLo;
            float _TermHi;
            float _SpecStrength;
            float _ReflStrength;
            float _GlossMul;
            float4 _RimColor;
            float4 _Emission;
            float _WorldUV;
            float4 _FlashColor;
            float _ShadowStrength;
            float _DustAmount;
            float _AOFloor;
            float _AOHeight;
            float _Saturation;
            float _Alpha;
        CBUFFER_END

        TEXTURE2D(_BaseMap);
        SAMPLER(sampler_BaseMap);
        TEXTURE2D(_BumpMap);
        SAMPLER(sampler_BumpMap);
        TEXTURE2D(_MetallicGlossMap);
        SAMPLER(sampler_MetallicGlossMap);
        TEXTURE2D(_OcclusionMap);
        SAMPLER(sampler_OcclusionMap);

        // The optional variant leaves generated meshes and the imported level on their original path.
        // Match MikkTSpace: keep the handedness of mirrored transforms when reconstructing the bitangent.
        half3 BakedWorldNormal(half3 normalWS, half4 tangentWS, float2 uv)
        {
            half3 n = normalize(normalWS);
        #if defined(_BAKED_MAPS)
            if (_UseBakedMaps > 0.5)
            {
                half3 tangent = normalize(tangentWS.xyz - n * dot(n, tangentWS.xyz));
                half3 bitangent = cross(n, tangent) * tangentWS.w;
                half3 normalTS = UnpackNormalScale(SAMPLE_TEXTURE2D(_BumpMap, sampler_BumpMap, uv), _BumpScale);
                n = normalize(tangent * normalTS.x + bitangent * normalTS.y + n * normalTS.z);
            }
        #endif
            return n;
        }

        // Globals (set from script): hemisphere fill multipliers, procedural sky for reflections, dust tint.
        float4 _ToonAmbientSky;
        float4 _ToonAmbientGround;
        float4 _EnvZenith;
        float4 _EnvHorizon;
        float4 _EnvGround;
        float4 _DustColor;

        // Underground floors (oriented rects, see Ground.ShaderRegions): dust and ground contact are measured from the
        // floor a vertex stands on, so tunnels and the sunken hangar look like the surface does.
        // A = (center x, center z, cos yaw, sin yaw), B = (half x, half z, height at -z end, height at +z end)
        float4 _RGFloorA[12];
        float4 _RGFloorB[12];
        float _RGFloorCount;

        float FloorBelow(float3 p)
        {
            float fy = 0.0;
            int n = (int)_RGFloorCount;
            for (int k = 0; k < 12; k++)
            {
                if (k >= n) break;
                float4 A = _RGFloorA[k];
                float4 B = _RGFloorB[k];
                float2 d = p.xz - A.xy;
                float lx = d.x * A.z - d.y * A.w;
                float lz = d.x * A.w + d.y * A.z;
                if (abs(lx) <= B.x && abs(lz) <= B.y)
                {
                    float h = lerp(B.z, B.w, saturate((lz + B.y) / max(2.0 * B.y, 0.01)));
                    if (p.y < h + 4.0) fy = min(fy, h);
                }
            }
            return fy;
        }
        ENDHLSL

        // ------------------------------------------------------------------ Main lit pass
        Pass
        {
            Name "ForwardStylized"
            Tags { "LightMode"="UniversalForward" }
            Cull Back
            Blend [_SrcBlend] [_DstBlend]
            ZWrite [_ZWrite]

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            // Runtime-created car materials need this variant retained in player builds.
            #pragma multi_compile_local _ _BAKED_MAPS
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
            #if defined(_BAKED_MAPS)
                float4 tangentOS  : TANGENT;
            #endif
                float4 color      : COLOR;
                float2 uv         : TEXCOORD0;
                float2 matParams  : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3  normalWS   : TEXCOORD1;
                float2 uv         : TEXCOORD2;
                half   fogFactor  : TEXCOORD3;
                half2  matParams  : TEXCOORD4;
                float  localY     : TEXCOORD5;   // height above the floor the vertex stands on
                half4  color      : COLOR;
            #if defined(_BAKED_MAPS)
                half4  tangentWS  : TEXCOORD6;
            #endif
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings vert (Attributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
            #if defined(_BAKED_MAPS)
                o.tangentWS = half4(TransformObjectToWorldDir(v.tangentOS.xyz), v.tangentOS.w * GetOddNegativeScale());
            #endif
                o.matParams = v.matParams;
                o.color = v.color;
                o.uv = (_WorldUV > 0.0) ? p.positionWS.xz * _WorldUV : TRANSFORM_TEX(v.uv, _BaseMap);
                o.fogFactor = ComputeFogFactor(p.positionCS.z);
                o.localY = p.positionWS.y - FloorBelow(p.positionWS);
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half3 n = normalize(i.normalWS);
                float3 viewDir = normalize(GetWorldSpaceViewDir(i.positionWS));
            #if defined(_MAIN_LIGHT_SHADOWS_SCREEN)
                float4 shadowCoord = ComputeScreenPos(TransformWorldToHClip(i.positionWS));
            #else
                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
            #endif
                Light mainLight = GetMainLight(shadowCoord);

                half4 tex = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv);
                // Baked maps already contain the palette. Vertex alpha remains the self-lit mask below.
                half3 albedo = tex.rgb * _BaseColor.rgb * lerp(half3(1, 1, 1), i.color.rgb, _VertexColorWeight);
                half lum = dot(albedo, half3(0.2126, 0.7152, 0.0722));
                albedo = max(lerp(lum.xxx, albedo, _Saturation), 0.0);
                half gloss = saturate(i.matParams.x * _GlossMul);
                half metal = saturate(i.matParams.y);
                half bakedAO = 1.0;
            #if defined(_BAKED_MAPS)
                if (_UseBakedMaps > 0.5)
                {
                    n = BakedWorldNormal(i.normalWS, i.tangentWS, i.uv);
                    half4 surface = SAMPLE_TEXTURE2D(_MetallicGlossMap, sampler_MetallicGlossMap, i.uv);
                    gloss = saturate(surface.a * _GlossMul);
                    metal = saturate(surface.r);
                    bakedAO = lerp(1.0, SAMPLE_TEXTURE2D(_OcclusionMap, sampler_OcclusionMap, i.uv).r, _OcclusionStrength);
                }
            #endif
                half selfLit = saturate(1.0 - i.color.a);

                // broad painted dust gradient on the lowest part of objects (no noise)
                half dustH = saturate(1.0 - i.localY * 1.1);
                albedo = lerp(albedo, _DustColor.rgb, dustH * dustH * _DustAmount * (1.0 - selfLit));
                gloss *= 1.0 - dustH * _DustAmount * 0.6;

                // ---- soft diffuse: wide terminator, no bands
                half ndl = dot(n, mainLight.direction);
                half diff = smoothstep(_TermLo, _TermHi, ndl);
                half sh = lerp(1.0, mainLight.shadowAttenuation, _ShadowStrength);
                half direct = diff * sh;

                // shade = zone tint x hemisphere fill (cool from the sky, warm bounce from the ground);
                // faces turned fully away get a touch more depth so rounded forms keep their volume
                half up = saturate(n.y * 0.5 + 0.5);
                half3 hemi = lerp(_ToonAmbientGround.rgb, _ToonAmbientSky.rgb, up);
                half3 shade = _ShadeColor.rgb * hemi * lerp(0.82, 1.0, saturate(ndl + 1.0));
                half3 lightCol = mainLight.color;

                // Baked cavity occlusion belongs to the soft fill, leaving direct sun and lamps clear.
                half ao = bakedAO;
            #if defined(_SCREEN_SPACE_OCCLUSION)
                AmbientOcclusionFactor ssao = GetScreenSpaceAmbientOcclusion(GetNormalizedScreenSpaceUV(i.positionCS));
                ao *= ssao.indirectAmbientOcclusion;
                direct *= lerp(1.0, ssao.directAmbientOcclusion, 0.5);
            #endif
                half3 col = albedo * lerp(shade * ao, lightCol, direct);

                // soft ground contact occlusion: objects settle into the ground
                col *= lerp(_AOFloor, 1.0, saturate(i.localY / max(_AOHeight, 0.01)));

                half NoV = saturate(dot(n, viewDir));
                half fres = pow(1.0 - NoV, 3.0);

                // ---- sky reflection (stylized two-tone environment), only for glossy parts
                if (gloss > 0.02)
                {
                    float3 R = reflect(-viewDir, n);
                    half3 sky = lerp(_EnvHorizon.rgb, _EnvZenith.rgb, saturate(R.y * 1.6));
                    half3 env = lerp(_EnvGround.rgb, sky, smoothstep(-0.12, 0.18, R.y));
                    half refl = gloss * lerp(0.02 + 0.42 * fres, 0.45 + 0.35 * fres, metal) * _ReflStrength;
                    half3 tint = lerp(half3(1, 1, 1), saturate(albedo * 1.6 + 0.06), metal);
                    col = lerp(col, env * tint * lerp(0.62, 1.0, sh), saturate(refl));
                }

                // ---- broad stylized highlight: soft-edged, its size follows the gloss. It is computed for a lower
                //      "key" light at the sun's azimuth, so with the high sun and the high camera it lands as a band
                //      on rounded shoulders and slopes facing the light instead of washing over every flat top.
                {
                    half3 keyDir = normalize(half3(mainLight.direction.x, mainLight.direction.y * 0.4, mainLight.direction.z));
                    half3 h = normalize(keyDir + viewDir);
                    half ndh = saturate(dot(n, h));
                    half center = lerp(0.82, 0.975, gloss);
                    half width = lerp(0.15, 0.022, gloss);
                    half spec = smoothstep(center - width, center + width, ndh);
                    spec *= lerp(0.03, 0.36, gloss) * (1.0 + metal * 0.7) * _SpecStrength;
                    half3 specCol = lerp(half3(1.0, 0.97, 0.9), saturate(albedo * 1.8 + 0.15), metal);
                    col += lightCol * specCol * spec * direct;
                }

                // ---- soft rim separates silhouettes from the ground
                half rim = pow(1.0 - NoV, 4.0) * _RimColor.a;
                col += _RimColor.rgb * rim * (0.35 + 0.65 * direct) * (0.4 + lum);

                col += _Emission.rgb;
                col = lerp(col, albedo * 1.5, selfLit);
                // hit flash brightens the object's own colors (it keeps its identity instead of turning into a white ghost)
                col = col * (1.0 + _FlashColor.a * 1.5) + _FlashColor.rgb * (_FlashColor.a * 0.1);
                col = MixFog(col, i.fogFactor);
                return half4(col, _Alpha);
            }
            ENDHLSL
        }

        // ------------------------------------------------------------------ Shadow caster
        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode"="ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vertShadow
            #pragma fragment fragShadow
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct AttributesS
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct VaryingsS
            {
                float4 positionCS : SV_POSITION;
            };

            VaryingsS vertShadow (AttributesS v)
            {
                VaryingsS o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 posWS = TransformObjectToWorld(v.positionOS.xyz);
                float3 nWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - posWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                float4 posCS = TransformWorldToHClip(ApplyShadowBias(posWS, nWS, lightDir));
            #if UNITY_REVERSED_Z
                posCS.z = min(posCS.z, UNITY_NEAR_CLIP_VALUE);
            #else
                posCS.z = max(posCS.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = posCS;
                return o;
            }

            half4 fragShadow (VaryingsS i) : SV_Target { return 0; }
            ENDHLSL
        }

        // ------------------------------------------------------------------ Depth only
        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode"="DepthOnly" }
            ZWrite On
            ColorMask R
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vertDepth
            #pragma fragment fragDepth
            #pragma multi_compile_instancing

            struct AttributesD { float4 positionOS : POSITION; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct VaryingsD { float4 positionCS : SV_POSITION; };

            VaryingsD vertDepth (AttributesD v)
            {
                VaryingsD o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                return o;
            }
            half fragDepth (VaryingsD i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }

        // ------------------------------------------------------------------ Depth normals (SSAO on the PC renderer)
        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode"="DepthNormals" }
            ZWrite On
            Cull Back

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vertDN
            #pragma fragment fragDN
            #pragma multi_compile_instancing
            #pragma multi_compile_local _ _BAKED_MAPS

            struct AttributesN
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
            #if defined(_BAKED_MAPS)
                float4 tangentOS : TANGENT;
                float2 uv : TEXCOORD0;
            #endif
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct VaryingsN
            {
                float4 positionCS : SV_POSITION;
                float3 normalWS : TEXCOORD0;
            #if defined(_BAKED_MAPS)
                half4 tangentWS : TEXCOORD1;
                float2 uv : TEXCOORD2;
            #endif
            };

            VaryingsN vertDN (AttributesN v)
            {
                VaryingsN o;
                UNITY_SETUP_INSTANCE_ID(v);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
            #if defined(_BAKED_MAPS)
                o.tangentWS = half4(TransformObjectToWorldDir(v.tangentOS.xyz), v.tangentOS.w * GetOddNegativeScale());
                float3 positionWS = TransformObjectToWorld(v.positionOS.xyz);
                o.uv = (_WorldUV > 0.0) ? positionWS.xz * _WorldUV : TRANSFORM_TEX(v.uv, _BaseMap);
            #endif
                return o;
            }
            half4 fragDN (VaryingsN i) : SV_Target
            {
            #if defined(_BAKED_MAPS)
                return half4(BakedWorldNormal(i.normalWS, i.tangentWS, i.uv), 0.0);
            #else
                return half4(normalize(i.normalWS), 0.0);
            #endif
            }
            ENDHLSL
        }
    }
    FallBack Off
}
