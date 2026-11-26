// Append this material to an existing one-submesh procedural MeshRenderer for comic previews.
// A separate renderer material guarantees URP submits the ink as its own forward draw.
Shader "Hidden/RoadGame/ArtDirectionInk"
{
    Properties
    {
        _OutlineColor ("Ink Color", Color) = (0.035,0.050,0.070,1)
        _OutlineWidth ("Ink Width In Pixels", Range(0,8)) = 3.5
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry+1" }
        Pass
        {
            Name "InkHull"
            Tags { "LightMode"="UniversalForward" }
            Cull Front
            ZWrite Off
            ZTest LEqual

            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex InkVertex
            #pragma fragment InkFragment
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _OutlineColor;
                float _OutlineWidth;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float4 color : COLOR;
                float3 smoothNormalOS : TEXCOORD3;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float fogFactor : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings InkVertex(Attributes input)
            {
                Varyings output = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                float3 normalOS = dot(input.smoothNormalOS, input.smoothNormalOS) > 0.01
                    ? input.smoothNormalOS : input.normalOS;
                float3 normalWS = TransformObjectToWorldNormal(normalOS);
                float4 positionCS = TransformObjectToHClip(input.positionOS.xyz);
                float2 direction = mul((float3x3)UNITY_MATRIX_VP, normalWS).xy;
                direction /= max(length(direction), 1e-4);
                // Original COLOR.a marks emissive lamps/crystals; their ink remains slightly finer.
                float width = _OutlineWidth * lerp(0.65, 1.0, saturate(input.color.a));
                positionCS.xy += direction * (2.0 / max(_ScreenParams.xy, float2(1,1))) * width * positionCS.w;
                output.positionCS = positionCS;
                output.fogFactor = ComputeFogFactor(positionCS.z);
                return output;
            }

            half4 InkFragment(Varyings input) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                return half4(MixFog(_OutlineColor.rgb, input.fogFactor), 1.0);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
