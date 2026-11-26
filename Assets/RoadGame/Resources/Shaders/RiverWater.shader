// A single inexpensive forward pass: analytic flowing ripples, soft sun/sky reflection and no screen-space copies.
// Geometry displacement is strictly <= 0.012 m; the shallow drivable river bed remains the physics surface.
Shader "RoadGame/RiverWater"
{
    Properties
    {
        _BaseColor ("Art Tint", Color) = (1,1,1,1)
        _BaseMap ("Art Texture", 2D) = "white" {}
        _Alpha ("Water Opacity", Range(0,1)) = 0.62
        _ShadeColor ("Zone Shade", Color) = (0.66,0.62,0.82,1)
        _WaveAmplitude ("Wave Height", Range(0,0.012)) = 0.012
        _FlowDirection ("Flow Direction (XZ)", Vector) = (0.18,-1,0,0)
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent-80" }
        Pass
        {
            Name "RiverWater"
            Tags { "LightMode"="UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            HLSLPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseColor;
                float4 _BaseMap_ST;
                float4 _ShadeColor;
                float4 _FlowDirection;
                float _Alpha;
                float _WaveAmplitude;
            CBUFFER_END
            struct Attributes { float4 positionOS : POSITION; float4 color : COLOR; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3 artColor : TEXCOORD1;
                half fogFactor : TEXCOORD2;
            };
            Varyings vert(Attributes v)
            {
                Varyings o;
                float3 p = TransformObjectToWorld(v.positionOS.xyz);
                float2 q = p.xz - _FlowDirection.xy * (_Time.y * 0.65);
                p.y += min(_WaveAmplitude, 0.012) * (sin(q.x * 2.1 + q.y * 1.5) * 0.6 + sin(q.x * -1.2 + q.y * 2.8) * 0.4);
                o.positionWS = p;
                o.positionCS = TransformWorldToHClip(p);
                o.artColor = v.color.rgb * _BaseColor.rgb;
                o.fogFactor = ComputeFogFactor(o.positionCS.z);
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                float2 q = i.positionWS.xz - _FlowDirection.xy * (_Time.y * 0.65);
                // Two crossing wave families continuously move the highlights instead of scrolling a road texture.
                float a = q.x * 2.1 + q.y * 1.5 + sin(q.y * 0.41) * 0.7;
                float b = q.x * -1.2 + q.y * 2.8;
                float2 slope = float2(cos(a) * 0.10 - cos(b) * 0.065, cos(a) * 0.065 + cos(b) * 0.12);
                half3 n = normalize(half3(-slope.x, 1.0, -slope.y));
                half3 view = SafeNormalize(GetWorldSpaceViewDir(i.positionWS));
                Light sun = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                half direct = saturate(dot(n, sun.direction)) * lerp(0.48, 1.0, sun.shadowAttenuation);
                half fresnel = pow(1.0 - saturate(dot(n, view)), 3.0);
                half3 body = lerp(i.artColor, half3(0.20,0.48,0.49), 0.42);
                half3 col = body * (half3(0.48,0.61,0.63) + sun.color * direct * 0.50);
                col += half3(0.20,0.34,0.39) * (0.13 + fresnel * 0.50);
                half nh = saturate(dot(n, SafeNormalize(view + sun.direction)));
                half spec = pow(nh, 72.0) * 0.42 * sun.shadowAttenuation;
                col += sun.color * half3(1.0,0.97,0.84) * spec;
                // Broad, broken crest glints remain readable at the top-down gameplay zoom.
                half crest = smoothstep(0.86, 0.99, sin(a)) * smoothstep(-0.1,0.65,sin(b * 0.47 + _Time.y * 0.23));
                col += half3(0.53,0.72,0.70) * crest * 0.17;
                col = MixFog(col, i.fogFactor);
                return half4(col, saturate(_Alpha + fresnel * 0.14 + crest * 0.04));
            }
            ENDHLSL
        }
    }
    FallBack Off
}
