// Murky swamp water for the second zone (Toxic Wetlands). One cheap forward pass, mobile friendly:
// - body colour from the vertex colour (lighter olive at the banks, dark in the middle), tinted by _BaseColor;
// - floating algae / scum from a small tileable noise map (_BaseMap, R) drifting very slowly;
// - gentle analytic ripples (geometry displacement <= 0.006 m; the shallow bed stays the physics surface),
//   soft sun light with received shadows, a quiet sky reflection at grazing angles;
// - vertex colour alpha = toxicity: a local yellow-green glow near leaking pipes and drums (not the whole pond).
Shader "RoadGame/SwampWater"
{
    Properties
    {
        _BaseColor ("Art Tint", Color) = (1,1,1,1)
        _BaseMap ("Scum Noise (R)", 2D) = "gray" {}
        _Alpha ("Water Opacity", Range(0,1)) = 0.84
        _ShadeColor ("Zone Shade", Color) = (0.66,0.62,0.82,1)
        _ScumColor ("Floating Algae", Color) = (0.46,0.56,0.19,1)
        _ToxicColor ("Toxic Glow", Color) = (0.72,0.95,0.26,1)
        _SkyColor ("Sky Reflection", Color) = (0.70,0.76,0.72,1)
        _WaveAmplitude ("Wave Height", Range(0,0.006)) = 0.004
        _Drift ("Drift (XZ m/s)", Vector) = (0.035,0.02,0,0)
    }
    SubShader
    {
        Tags { "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent-80" }
        Pass
        {
            Name "SwampWater"
            Tags { "LightMode"="UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Back
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
                float4 _ScumColor;
                float4 _ToxicColor;
                float4 _SkyColor;
                float4 _Drift;
                float _Alpha;
                float _WaveAmplitude;
            CBUFFER_END
            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            struct Attributes { float4 positionOS : POSITION; float4 color : COLOR; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half4 color : TEXCOORD1;
                half fogFactor : TEXCOORD2;
            };
            Varyings vert(Attributes v)
            {
                Varyings o;
                float3 p = TransformObjectToWorld(v.positionOS.xyz);
                float t = _Time.y;
                p.y += min(_WaveAmplitude, 0.006) * (sin(p.x * 1.3 + p.z * 0.9 + t * 0.8) * 0.6 + sin(p.x * -0.7 + p.z * 1.6 + t * 0.6) * 0.4);
                o.positionWS = p;
                o.positionCS = TransformWorldToHClip(p);
                o.color = half4(v.color.rgb * _BaseColor.rgb, v.color.a);
                o.fogFactor = ComputeFogFactor(o.positionCS.z);
                return o;
            }
            half4 frag(Varyings i) : SV_Target
            {
                float2 q = i.positionWS.xz;
                float t = _Time.y;
                // slow scum: two scales of the noise map drifting against each other
                half n1 = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, (q + _Drift.xy * t) * 0.065).r;
                half n2 = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, (q - _Drift.yx * t * 1.4) * 0.19 + 0.37).r;
                half scumField = n1 * 0.68 + n2 * 0.32;
                half scum = smoothstep(0.60, 0.70, scumField);
                half scumEdge = smoothstep(0.56, 0.62, scumField) - scum;
                // gentle ripples: two crossing wave families (only on open water)
                float a = q.x * 1.7 + q.y * 1.1 + t * 0.9;
                float b = q.x * -0.8 + q.y * 2.0 + t * 0.7;
                float2 slope = float2(cos(a) * 0.05 - cos(b) * 0.03, cos(a) * 0.03 + cos(b) * 0.06) * (1.0 - scum);
                half3 n = normalize(half3(-slope.x, 1.0, -slope.y));
                half3 view = SafeNormalize(GetWorldSpaceViewDir(i.positionWS));
                Light sun = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                half sh = lerp(0.55, 1.0, sun.shadowAttenuation);
                half diff = saturate(dot(n, sun.direction)) * sh;
                half3 ambient = _ShadeColor.rgb * 0.72;
                half3 body = i.color.rgb;
                half3 col = body * (ambient + sun.color * diff * 0.55);
                half fresnel = pow(1.0 - saturate(dot(n, view)), 4.0);
                col = lerp(col, _SkyColor.rgb * (0.55 + 0.45 * sh), fresnel * 0.55 * (1.0 - scum));
                half nh = saturate(dot(n, SafeNormalize(view + sun.direction)));
                col += sun.color * half3(1.0, 0.98, 0.88) * pow(nh, 90.0) * 0.30 * sun.shadowAttenuation * (1.0 - scum);
                // floating algae: matte, a slightly lighter rim around each patch
                half3 scumCol = _ScumColor.rgb * (1.0 + 0.18 * (n2 - 0.5)) * (ambient + sun.color * saturate(sun.direction.y) * sh * 0.75);
                col = lerp(col, scumCol, saturate(scum * 0.9 + scumEdge * 0.35));
                // local toxicity (vertex alpha): glow pulses softly, never over the whole pond
                half tox = saturate(i.color.a);
                half pulse = 0.75 + 0.25 * sin(t * 1.6 + n1 * 9.0);
                col = lerp(col, _ToxicColor.rgb * (0.58 + 0.2 * pulse), tox * 0.36);
                col += _ToxicColor.rgb * tox * 0.05 * pulse;
                col = MixFog(col, i.fogFactor);
                half alpha = saturate(_Alpha + scum * 0.12 + fresnel * 0.08 + tox * 0.08);
                return half4(col, alpha);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
