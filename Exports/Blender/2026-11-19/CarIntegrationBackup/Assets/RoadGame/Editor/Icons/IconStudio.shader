// Icon studio lighting (editor only, used to bake the UI icon sprites). Toy-like "casual icon" shading:
// - soft wrapped key light with a smooth S-curve, received self-shadows (soft), optional SSAO;
// - the shadowed side is a darker, more saturated and slightly cooler version of the color (juicy, never grey);
// - broad soft-edged highlights whose size follows the per-vertex gloss (UV1.x), a clear-coat top sheen;
// - metals (UV1.y) reflect a two-tone studio environment tinted by their color;
// - a rim light from behind for thickness. Vertex alpha < 1 = self-lit (sparks, glows).
// All values come from globals set by IconStudio.cs, so every icon is lit by exactly the same studio.
Shader "Hidden/RoadGame/IconStudio"
{
    Properties { }

    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        float4 _IcoKeyColor;     // key light color (linear) * intensity
        float4 _IcoSkyColor;     // fill from above
        float4 _IcoGroundColor;  // warm bounce from below
        float4 _IcoShadowTint;   // multiplies the shadowed side
        float4 _IcoRimColor;     // rgb, a = strength
        float4 _IcoRimDir;       // xyz towards the rim light
        float4 _IcoEnvTop;       // metal reflections: studio top / bottom
        float4 _IcoEnvBottom;
        float4 _IcoParams;       // x = wrap, y = highlight strength, z = received shadow strength, w = SSAO strength
        float4 _IcoParams2;      // x = shadow-side saturation boost, y = clear-coat sheen, z = rim from all sides
        ENDHLSL

        Pass
        {
            Name "IconLit"
            Tags { "LightMode"="UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float4 color      : COLOR;
                float2 matParams  : TEXCOORD1;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3  normalWS   : TEXCOORD1;
                half2  matParams  : TEXCOORD2;
                half4  color      : COLOR;
            };

            Varyings vert (Attributes v)
            {
                Varyings o = (Varyings)0;
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.matParams = v.matParams;
                o.color = v.color;
                return o;
            }

            half4 frag (Varyings i) : SV_Target
            {
                half3 n = normalize(i.normalWS);
                float3 V = normalize(GetWorldSpaceViewDir(i.positionWS));
            #if defined(_MAIN_LIGHT_SHADOWS_SCREEN)
                float4 shadowCoord = ComputeScreenPos(TransformWorldToHClip(i.positionWS));
            #else
                float4 shadowCoord = TransformWorldToShadowCoord(i.positionWS);
            #endif
                Light L = GetMainLight(shadowCoord);

                half3 albedo = i.color.rgb;
                half gloss = saturate(i.matParams.x);
                half metal = saturate(i.matParams.y);
                half selfLit = saturate(1.0 - i.color.a);

                // ---- key light: wrapped, smooth S-curve (soft gradient, clear form)
                half ndl = dot(n, L.direction);
                half wrap = _IcoParams.x;
                half diff = saturate((ndl + wrap) / (1.0 + wrap));
                diff = diff * diff * (3.0 - 2.0 * diff);
                half sh = lerp(1.0, L.shadowAttenuation, _IcoParams.z);
                half direct = diff * sh;

                // ---- shadow side: deeper, more saturated, slightly cooler version of the color + hemisphere fill
                half3 deep = albedo * albedo;
                half3 shadeAlb = lerp(albedo, deep, _IcoParams2.x);
                half up = saturate(n.y * 0.5 + 0.5);
                half3 hemi = lerp(_IcoGroundColor.rgb, _IcoSkyColor.rgb, up);
                half ao = 1.0;
            #if defined(_SCREEN_SPACE_OCCLUSION)
                AmbientOcclusionFactor ssao = GetScreenSpaceAmbientOcclusion(GetNormalizedScreenSpaceUV(i.positionCS));
                ao = lerp(1.0, ssao.indirectAmbientOcclusion, _IcoParams.w);
                direct *= lerp(1.0, ssao.directAmbientOcclusion, 0.35 * _IcoParams.w);
            #endif
                half3 shadowSide = shadeAlb * _IcoShadowTint.rgb * hemi * ao;
                half3 lit = albedo * _IcoKeyColor.rgb * lerp(0.92, 1.0, ao);
                half3 col = lerp(shadowSide, lit, direct);

                half NoV = saturate(dot(n, V));
                half fres = pow(1.0 - NoV, 3.0);
                float3 R = reflect(-V, n);

                // ---- metals: two-tone studio environment tinted by the metal color
                half envT = smoothstep(-0.35, 0.5, R.y);
                half3 env = lerp(_IcoEnvBottom.rgb, _IcoEnvTop.rgb, envT);
                half3 metalCol = albedo * env * (0.6 + 0.4 * sh);
                col = lerp(col, metalCol, metal * 0.65);

                // ---- clear-coat sheen on the upper side of glossy surfaces
                col += _IcoParams2.y * gloss * (1.0 - metal * 0.5) * smoothstep(0.3, 0.95, R.y) * (0.45 + 0.55 * sh) * (0.5 + 0.5 * fres);

                // ---- broad stylized highlight (soft edge, size by gloss)
                half3 H = normalize(L.direction + V);
                half ndh = saturate(dot(n, H));
                half s = pow(ndh, lerp(10.0, 150.0, gloss));
                half spec = smoothstep(0.16, 0.6, s) * lerp(0.06, 0.9, gloss) * _IcoParams.y;
                half3 specCol = lerp(half3(1.0, 0.98, 0.94), saturate(albedo * 1.5 + 0.3), metal * 0.75);
                col += specCol * spec * sh;

                // ---- rim light from behind: thickness and separation on any background
                half rimSide = saturate(dot(n, normalize(_IcoRimDir.xyz)) * 0.6 + 0.4 + _IcoParams2.z);
                col += _IcoRimColor.rgb * _IcoRimColor.a * fres * rimSide * (0.6 + 0.4 * gloss);

                col = lerp(col, albedo * 1.3 + 0.08, selfLit);
                return half4(max(col, 0.0), 1.0);
            }
            ENDHLSL
        }

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
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct AttributesS { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct VaryingsS { float4 positionCS : SV_POSITION; };

            VaryingsS vertShadow (AttributesS v)
            {
                VaryingsS o;
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
            struct AttributesD { float4 positionOS : POSITION; };
            struct VaryingsD { float4 positionCS : SV_POSITION; };
            VaryingsD vertDepth (AttributesD v) { VaryingsD o; o.positionCS = TransformObjectToHClip(v.positionOS.xyz); return o; }
            half fragDepth (VaryingsD i) : SV_Target { return i.positionCS.z; }
            ENDHLSL
        }

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
            struct AttributesN { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct VaryingsN { float4 positionCS : SV_POSITION; float3 normalWS : TEXCOORD0; };
            VaryingsN vertDN (AttributesN v)
            {
                VaryingsN o;
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                return o;
            }
            half4 fragDN (VaryingsN i) : SV_Target { return half4(normalize(i.normalWS), 0.0); }
            ENDHLSL
        }
    }
    FallBack Off
}
