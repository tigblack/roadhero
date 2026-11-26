// Dedicated editor preview inspired by the clean forms and painted gradients in Habby's
// official Archero 2 gameplay screenshots. These are the project's own meshes and colors.
// No outlines, grit, sampled material wear, photoreal reflections or pixel quantization.
Shader "Hidden/RoadGame/ArcheroDirection"
{
    Properties
    {
        _Ground ("Surface Kind (0 Object, 1 Terrain, 2 Road)", Float) = 0
        _BaseColor ("Base Color", Color) = (1,1,1,1)
        _BaseMap ("Original Base Map", 2D) = "white" {}
        _WorldUV ("World XZ UV Scale", Float) = 0
        _GlossMul ("UV1 Gloss Multiplier", Range(0,2)) = 1
        _ShadowStrength ("Received Shadow Strength", Range(0,1)) = 1
        _AOFloor ("Original Contact Value", Range(0,1)) = 0.6
        _FloorTint ("Pastel Desert Floor", Color) = (0.94,0.83,0.66,1)
        _RoadTint ("Quiet Lilac Stone Road", Color) = (0.53,0.50,0.60,1)
        _LaneTint ("Cream Gold Road Markings", Color) = (1.0,0.89,0.53,1)
        _UndersideTint ("Painted Violet Undersides", Color) = (0.73,0.67,0.91,1)
        _HighlightTint ("Broad Cream Highlight", Color) = (1.0,0.97,0.87,1)
        _ContactStrength ("Soft Painted Contact AO", Range(0,0.5)) = 0.20
        _Brightness ("Soft Light Brightness", Range(0.5,1.5)) = 1.05
        _FlashColor ("Original Hit Flash", Color) = (1,1,1,0)
        _Emission ("Original Emission", Color) = (0,0,0,0)
        // Kept for the preview helper's material-copy contract; deliberately unused by this clean style.
        _DetailMap ("Original Detail Map (Not Used)", 2D) = "gray" {}
        _DetailStrength ("Original Detail Strength (Not Used)", Float) = 0
    }

    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseColor;
            float4 _BaseMap_ST;
            float4 _BaseMap_TexelSize;
            float4 _FloorTint;
            float4 _RoadTint;
            float4 _LaneTint;
            float4 _UndersideTint;
            float4 _HighlightTint;
            float4 _FlashColor;
            float4 _Emission;
            float4 _DetailMap_ST;
            float _Ground;
            float _WorldUV;
            float _GlossMul;
            float _ShadowStrength;
            float _AOFloor;
            float _ContactStrength;
            float _Brightness;
            float _DetailStrength;
        CBUFFER_END

        TEXTURE2D(_BaseMap);
        SAMPLER(sampler_BaseMap);

        struct Attributes
        {
            float4 positionOS : POSITION;
            float3 normalOS : NORMAL;
            float4 color : COLOR;
            float2 uv : TEXCOORD0;
            float2 matParams : TEXCOORD1;
            UNITY_VERTEX_INPUT_INSTANCE_ID
        };

        struct Varyings
        {
            float4 positionCS : SV_POSITION;
            float3 positionWS : TEXCOORD0;
            float3 normalWS : TEXCOORD1;
            float2 uv : TEXCOORD2;
            float2 matParams : TEXCOORD3;
            float fogFactor : TEXCOORD4;
            float4 color : COLOR;
            UNITY_VERTEX_INPUT_INSTANCE_ID
            UNITY_VERTEX_OUTPUT_STEREO
        };

        Varyings Vert(Attributes input)
        {
            Varyings output = (Varyings)0;
            UNITY_SETUP_INSTANCE_ID(input);
            UNITY_TRANSFER_INSTANCE_ID(input, output);
            UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
            VertexPositionInputs position = GetVertexPositionInputs(input.positionOS.xyz);
            output.positionCS = position.positionCS;
            output.positionWS = position.positionWS;
            output.normalWS = TransformObjectToWorldNormal(input.normalOS);
            output.uv = _WorldUV > 0.0 ? position.positionWS.xz * _WorldUV : TRANSFORM_TEX(input.uv, _BaseMap);
            output.matParams = input.matParams;
            output.color = input.color;
            output.fogFactor = ComputeFogFactor(position.positionCS.z);
            return output;
        }

        float3 ToDisplay(float3 color) { return pow(max(color, 0.0), 1.0 / 2.2); }
        float3 ToLinear(float3 color) { return pow(max(color, 0.0), 2.2); }
        ENDHLSL

        Pass
        {
            Name "ArcheroPaintedForward"
            Tags { "LightMode"="UniversalForwardOnly" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            half4 Frag(Varyings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                float ground = step(0.5, _Ground);
                float terrain = ground * (1.0 - step(1.5, _Ground));
                float road = step(1.5, _Ground);
                float3 normalWS = normalize(input.normalWS);
                // Keep terrain's actual geometry, with a gently painted floor response rather than triangular noise.
                normalWS = normalize(lerp(normalWS, float3(0,1,0), terrain * 0.72));
                float3 view = normalize(GetWorldSpaceViewDir(input.positionWS));
                float4 shadowCoord;
                #if defined(_MAIN_LIGHT_SHADOWS_SCREEN)
                    shadowCoord = ComputeScreenPos(TransformWorldToHClip(input.positionWS));
                #else
                    shadowCoord = TransformWorldToShadowCoord(input.positionWS);
                #endif
                Light mainLight = GetMainLight(shadowCoord);
                float receivedShadow = lerp(1.0, mainLight.shadowAttenuation, _ShadowStrength);
                float ndl = dot(normalWS, mainLight.direction);
                float noV = saturate(dot(normalWS, view));
                float gloss = saturate(input.matParams.x * _GlossMul);
                float metal = saturate(input.matParams.y);

                // The existing road map still supplies its lane positions and broad edge shapes.
                // A low mip removes grain; terrain does not sample any wear/detail map.
                float3 map = road > 0.5
                    ? SAMPLE_TEXTURE2D_BIAS(_BaseMap, sampler_BaseMap, input.uv, 2.0).rgb
                    : SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, input.uv).rgb;
                float3 vertexAlbedo = max(input.color.rgb * _BaseColor.rgb, 0.0);
                float3 displayColor = ToDisplay(vertexAlbedo * map);
                if (terrain > 0.5)
                {
                    float3 nativeFloor = ToDisplay(vertexAlbedo);
                    displayColor = lerp(nativeFloor, ToDisplay(_FloorTint.rgb), 0.82);
                    // Only broad, low-contrast paint variation; no sand grain, checkerboard or new floor geometry.
                    float broadVariation = sin(input.positionWS.x * 0.055 + input.positionWS.z * 0.035) * 0.007;
                    displayColor += broadVariation;
                }
                else if (road > 0.5)
                {
                    float3 mapDisplay = ToDisplay(map);
                    float laneMask = smoothstep(0.23, 0.44, mapDisplay.r - mapDisplay.b)
                                   * smoothstep(0.47, 0.69, mapDisplay.g);
                    float originalTone = dot(mapDisplay, float3(0.30,0.59,0.11));
                    float roadPaint = clamp(originalTone - 0.45, -0.12, 0.12) * 0.14;
                    displayColor = lerp(ToDisplay(_RoadTint.rgb) + roadPaint, ToDisplay(_LaneTint.rgb), laneMask);
                }
                else
                {
                    // Preserve original material colors. The root may recolor selected mesh vertices for mint/coral accents.
                    float luma = dot(displayColor, float3(0.299,0.587,0.114));
                    displayColor = saturate(lerp(luma.xxx, displayColor, 1.06));
                    displayColor = saturate(displayColor * 0.94 + 0.045);
                }
                float3 albedo = ToLinear(saturate(displayColor));

                // Broad continuous form light: rounded painted objects, not the hard comic bands or shiny toy pass.
                float form = smoothstep(-0.58, 0.88, ndl);
                form = lerp(form, sqrt(saturate(form)), 0.28);
                float upward = saturate(normalWS.y * 0.5 + 0.5);
                float underside = (1.0 - form) * 0.76 + (1.0 - upward) * 0.24;
                float3 purplePaint = ToDisplay(_UndersideTint.rgb);
                float3 formTint = lerp(float3(1.0,0.985,0.94), purplePaint, underside);
                float gentleCastShadow = lerp(0.66, 1.0, receivedShadow);
                float3 shadowTint = lerp(float3(0.86,0.83,0.97), float3(1,1,1), receivedShadow);
                float3 lightTint = lerp(float3(1,1,1), mainLight.color, 0.26);
                float3 color = albedo * formTint * (0.64 + form * 0.47) * gentleCastShadow * shadowTint * lightTint;

                float paintedAO = 1.0;
                #if defined(_SCREEN_SPACE_OCCLUSION)
                    AmbientOcclusionFactor screenAO = GetScreenSpaceAmbientOcclusion(GetNormalizedScreenSpaceUV(input.positionCS));
                    paintedAO = lerp(0.76, 1.0, screenAO.indirectAmbientOcclusion);
                #endif
                float contact = 1.0 - (1.0 - saturate(input.positionWS.y * 0.9)) * _ContactStrength * (1.0 - ground);
                color *= paintedAO * contact;

                // Large cream highlights make rounded volumes readable without chrome reflections or hard specular dots.
                float3 halfVector = normalize(mainLight.direction + view);
                float ndh = saturate(dot(normalWS, halfVector));
                float broadHighlight = pow(ndh, lerp(12.0, 34.0, gloss));
                float highlightStrength = (0.018 + gloss * 0.17 + metal * 0.035) * (1.0 - ground);
                color += _HighlightTint.rgb * broadHighlight * highlightStrength * lerp(0.45,1.0,receivedShadow);
                float softRim = pow(1.0 - noV, 3.2) * (0.010 + gloss * 0.025) * (1.0 - ground);
                color += float3(0.68,0.86,0.86) * softRim * lerp(0.6,1.0,form);
                color *= _Brightness;

                color += _Emission.rgb;
                color = lerp(color, albedo * 1.6, saturate(1.0 - input.color.a));
                color = lerp(color, _FlashColor.rgb, saturate(_FlashColor.a));
                color = MixFog(color, input.fogFactor);
                return half4(max(color, 0.0), 1.0);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode"="ShadowCaster" }
            Cull Back
            ZWrite On
            ZTest LEqual
            ColorMask 0

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"
            float3 _LightDirection;
            float3 _LightPosition;
            struct ShadowVaryings { float4 positionCS : SV_POSITION; };

            ShadowVaryings ShadowVert(Attributes input)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                ShadowVaryings output;
                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(input.normalOS);
                #if defined(_CASTING_PUNCTUAL_LIGHT_SHADOW)
                    float3 direction = normalize(_LightPosition - positionWS);
                #else
                    float3 direction = _LightDirection;
                #endif
                float4 positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, direction));
                #if UNITY_REVERSED_Z
                    positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                    positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                output.positionCS = positionCS;
                return output;
            }
            half4 ShadowFrag(ShadowVaryings input) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode"="DepthOnly" }
            Cull Back
            ZWrite On
            ColorMask R
            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment DepthFrag
            #pragma multi_compile_instancing
            half4 DepthFrag(Varyings input) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode"="DepthNormalsOnly" }
            Cull Back
            ZWrite On
            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex Vert
            #pragma fragment NormalsFrag
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Packing.hlsl"

            half4 NormalsFrag(Varyings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                float3 normalWS = normalize(input.normalWS);
                float terrain = step(0.5, _Ground) * (1.0 - step(1.5, _Ground));
                normalWS = normalize(lerp(normalWS, float3(0,1,0), terrain * 0.72));
                #if defined(_GBUFFER_NORMALS_OCT)
                    float2 oct = saturate(PackNormalOctQuadEncode(normalWS) * 0.5 + 0.5);
                    return half4(PackFloat2To888(oct), 0);
                #else
                    return half4(normalWS, 0);
                #endif
            }
            ENDHLSL
        }
    }
    FallBack Off
}
