// Editor-only art-direction comparison. The model and vertex-color streams remain the game's own.
// _Style: 0 casual 3D, 1 weathered realistic, 2 faceted low poly, 3 comic/cel, 4 pixel palette.
// Pixel mode expects the preview camera's low-resolution target to be point-upscaled by the capture tool.
Shader "Hidden/RoadGame/ArtDirectionSurface"
{
    Properties
    {
        _Style ("Preview Style", Float) = 0
        _Ground ("Surface Kind (0 Object, 1 Terrain, 2 Road)", Float) = 0
        _BaseColor ("Base Color", Color) = (1,1,1,1)
        _BaseMap ("Base Map", 2D) = "white" {}
        _WorldUV ("World XZ UV Scale", Float) = 0
        _DetailMap ("Existing Grime / Scratch Map", 2D) = "gray" {}
        _DetailScale ("Grime Scale", Float) = 0.9
        _DetailStrength ("Grime Strength", Range(0,1)) = 0.55
        _DustAmount ("Dust Amount", Range(0,1)) = 0.42
        _DustTop ("Dust On Upward Faces", Range(0,1)) = 1
        _AOFloor ("Ground Contact Occlusion", Range(0,1)) = 0.6
        _GlossMul ("UV1 Gloss Multiplier", Range(0,2)) = 1
        _ReflBase ("Environment Reflection Base", Range(0,1)) = 0.1
        _ShadowStrength ("Received Shadow Strength", Range(0,1)) = 1
        _OutlineColor ("Comic Ink", Color) = (0.045,0.065,0.07,1)
        _OutlineWidth ("Comic Outline Width In Pixels", Float) = 3.4
        _FlashColor ("Hit Flash", Color) = (1,1,1,0)
        _Emission ("Emission", Color) = (0,0,0,0)
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
            float4 _DetailMap_ST;
            float4 _DetailMap_TexelSize;
            float4 _OutlineColor;
            float4 _FlashColor;
            float4 _Emission;
            float _Style;
            float _Ground;
            float _WorldUV;
            float _DetailScale;
            float _DetailStrength;
            float _DustAmount;
            float _DustTop;
            float _AOFloor;
            float _GlossMul;
            float _ReflBase;
            float _ShadowStrength;
            float _OutlineWidth;
        CBUFFER_END

        TEXTURE2D(_BaseMap);
        SAMPLER(sampler_BaseMap);
        TEXTURE2D(_DetailMap);
        SAMPLER(sampler_DetailMap);

        // The live game already supplies these globals through Mats.SetEnvironment/SetMood.
        float4 _ToonAmbientSky;
        float4 _ToonAmbientGround;
        float4 _EnvZenith;
        float4 _EnvHorizon;
        float4 _EnvGround;
        float4 _DustColor;

        struct ArtAttributes
        {
            float4 positionOS : POSITION;
            float3 normalOS : NORMAL;
            float4 color : COLOR;
            float2 uv : TEXCOORD0;
            float2 matParams : TEXCOORD1;
            float3 outlineNormalOS : TEXCOORD3;
            UNITY_VERTEX_INPUT_INSTANCE_ID
        };

        struct ArtVaryings
        {
            float4 positionCS : SV_POSITION;
            float3 positionWS : TEXCOORD0;
            float3 normalWS : TEXCOORD1;
            float3 positionOS : TEXCOORD2;
            float3 normalOS : TEXCOORD3;
            float2 uv : TEXCOORD4;
            float2 matParams : TEXCOORD5;
            float fogFactor : TEXCOORD6;
            float4 color : COLOR;
            UNITY_VERTEX_INPUT_INSTANCE_ID
            UNITY_VERTEX_OUTPUT_STEREO
        };

        ArtVaryings ArtVertex(ArtAttributes input)
        {
            ArtVaryings output = (ArtVaryings)0;
            UNITY_SETUP_INSTANCE_ID(input);
            UNITY_TRANSFER_INSTANCE_ID(input, output);
            UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
            VertexPositionInputs position = GetVertexPositionInputs(input.positionOS.xyz);
            output.positionCS = position.positionCS;
            output.positionWS = position.positionWS;
            output.normalWS = TransformObjectToWorldNormal(input.normalOS);
            output.positionOS = input.positionOS.xyz;
            output.normalOS = input.normalOS;
            output.uv = _WorldUV > 0.0 ? position.positionWS.xz * _WorldUV : TRANSFORM_TEX(input.uv, _BaseMap);
            output.matParams = input.matParams;
            output.color = input.color;
            output.fogFactor = ComputeFogFactor(position.positionCS.z);
            return output;
        }

        // The sign correction keeps flat normals consistent on mirrored model transforms and APIs.
        float3 FacetNormal(float3 positionWS, float3 referenceNormal)
        {
            float3 face = cross(ddy(positionWS), ddx(positionWS));
            float magnitudeSquared = dot(face, face);
            if (magnitudeSquared < 1e-14) return referenceNormal;
            face *= rsqrt(magnitudeSquared);
            return dot(face, referenceNormal) < 0.0 ? -face : face;
        }
        ENDHLSL

        Pass
        {
            Name "ArtDirectionForward"
            Tags { "LightMode"="UniversalForwardOnly" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex ArtVertex
            #pragma fragment ArtFragment
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            float3 ToDisplay(float3 linearColor) { return pow(max(linearColor, 0.0), 1.0 / 2.2); }
            float3 ToLinear(float3 displayColor) { return pow(max(displayColor, 0.0), 2.2); }

            float3 Environment(float3 reflectionDirection, float roughness)
            {
                float y = reflectionDirection.y;
                float3 sky = lerp(_EnvHorizon.rgb, _EnvZenith.rgb, saturate(y * 1.7));
                float3 reflection = lerp(_EnvGround.rgb, sky, smoothstep(-0.09, 0.14, y));
                float3 averageEnvironment = _EnvZenith.rgb * 0.30 + _EnvHorizon.rgb * 0.45 + _EnvGround.rgb * 0.25;
                return lerp(reflection, averageEnvironment, roughness * roughness * 0.8);
            }

            float Grime(float3 positionOS, float3 normalOS, float scale)
            {
                float3 weights = abs(normalize(normalOS));
                weights *= weights;
                weights *= weights;
                weights /= max(dot(weights, float3(1,1,1)), 1e-5);
                float3 p = positionOS * max(scale, 0.001);
                return SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, p.zy).r * weights.x
                     + SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, p.xz).r * weights.y
                     + SAMPLE_TEXTURE2D(_DetailMap, sampler_DetailMap, p.xy).r * weights.z;
            }

            // Surface-gradient bump needs neither an authored unwrap nor mesh tangents.
            // Thus detail remains attached to the existing procedural object-space geometry.
            float3 DetailNormal(float3 normalWS, float3 positionWS, float height)
            {
                float3 dx = ddx(positionWS);
                float3 dy = ddy(positionWS);
                float3 x = cross(dy, normalWS);
                float3 y = cross(normalWS, dx);
                float determinant = dot(dx, x);
                float3 gradient = sign(determinant) * (ddx(height) * x + ddy(height) * y);
                float3 result = abs(determinant) * normalWS - gradient;
                return dot(result, result) > 1e-15 ? normalize(result) : normalWS;
            }

            float BayerDither(float2 screenPosition)
            {
                int2 p = int2(fmod(floor(screenPosition), 4.0));
                const float4 row0 = float4(0,8,2,10);
                const float4 row1 = float4(12,4,14,6);
                const float4 row2 = float4(3,11,1,9);
                const float4 row3 = float4(15,7,13,5);
                float4 row = p.y == 0 ? row0 : (p.y == 1 ? row1 : (p.y == 2 ? row2 : row3));
                return ((row[p.x] + 0.5) / 16.0 - 0.5) * 0.01;
            }

            float3 PixelPalette(float3 linearColor, float2 screenPosition)
            {
                // A small, coherent wasteland palette, selected in display space after fog.
                const float3 palette[20] = {
                    float3(0.065,0.090,0.130), float3(0.130,0.180,0.220),
                    float3(0.230,0.270,0.290), float3(0.380,0.390,0.360),
                    float3(0.560,0.530,0.430), float3(0.690,0.630,0.490),
                    float3(0.820,0.730,0.540), float3(0.940,0.840,0.640),
                    float3(1.000,0.950,0.820), float3(0.250,0.360,0.320),
                    float3(0.350,0.510,0.390), float3(0.450,0.640,0.470),
                    float3(0.500,0.270,0.180), float3(0.720,0.370,0.220),
                    float3(0.920,0.540,0.280), float3(0.800,0.220,0.200),
                    float3(0.220,0.400,0.450), float3(0.360,0.620,0.670),
                    float3(0.780,0.650,0.290), float3(0.650,0.320,0.430)
                };
                float3 displayColor = saturate(ToDisplay(linearColor) + BayerDither(screenPosition));
                float nearest = 1e5;
                float3 chosen = palette[0];
                [unroll] for (int index = 0; index < 20; index++)
                {
                    float3 difference = displayColor - palette[index];
                    float distanceSquared = dot(difference * difference, float3(0.30,0.59,0.11));
                    if (distanceSquared < nearest) { nearest = distanceSquared; chosen = palette[index]; }
                }
                return ToLinear(chosen);
            }

            half4 ArtFragment(ArtVaryings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
                float3 normalWS = normalize(input.normalWS);
                if (_Style > 1.5 && _Style < 2.5) normalWS = FacetNormal(input.positionWS, normalWS);
                float3 view = normalize(GetWorldSpaceViewDir(input.positionWS));
                float4 shadowCoord;
                #if defined(_MAIN_LIGHT_SHADOWS_SCREEN)
                    shadowCoord = ComputeScreenPos(TransformWorldToHClip(input.positionWS));
                #else
                    shadowCoord = TransformWorldToShadowCoord(input.positionWS);
                #endif
                Light mainLight = GetMainLight(shadowCoord);
                float shadow = lerp(1.0, mainLight.shadowAttenuation, _ShadowStrength);
                float ground = step(0.5, _Ground);
                float terrain = ground * (1.0 - step(1.5, _Ground));
                float road = step(1.5, _Ground);
                float gloss = saturate(input.matParams.x * _GlossMul);
                float metal = saturate(input.matParams.y);
                float2 uv = input.uv;
                float3 textureColor;
                if (_Style > 3.5)
                {
                    // Point samples stay clean. A small road mip removes asphalt grain while keeping
                    // its real yellow markings, cracks and broad edge shapes from the existing map.
                    float mip = road * 2.0;
                    float2 size = max(_BaseMap_TexelSize.zw / exp2(mip), float2(1,1));
                    uv = (floor(uv * size) + 0.5) / size;
                    textureColor = SAMPLE_TEXTURE2D_LOD(_BaseMap, sampler_BaseMap, uv, mip).rgb;
                    textureColor = lerp(textureColor, float3(0.90,0.89,0.85), terrain * 0.96);
                }
                else if (_Style < 0.5 && terrain > 0.5)
                    textureColor = SAMPLE_TEXTURE2D_BIAS(_BaseMap, sampler_BaseMap, uv, 2).rgb;
                else textureColor = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, uv).rgb;

                if (_Style > 1.5 && _Style < 2.5) textureColor = lerp(textureColor, float3(1,1,1), terrain);
                if (_Style > 2.5 && _Style < 3.5) textureColor = lerp(textureColor, float3(1,1,1), terrain * 0.65);
                // All styles preserve the real model's vertex colors; the default white map is only a multiplier.
                float3 albedo = max(0.0, input.color.rgb * _BaseColor.rgb * textureColor);
                float3 halfVector = normalize(mainLight.direction + view);
                float ndl = dot(normalWS, mainLight.direction);
                float ndh = saturate(dot(normalWS, halfVector));
                float noV = saturate(dot(normalWS, view));
                float contact = lerp(_AOFloor, 1.0, saturate(input.positionWS.y * 1.6));
                contact = lerp(contact, 1.0, ground);
                float3 color;

                if (_Style < 0.5)
                {
                    // Smooth toy-like forms, clean saturated paint, broad plastic highlights, no ink or grain.
                    float3 displayColor = ToDisplay(albedo);
                    float luma = dot(displayColor, float3(0.299,0.587,0.114));
                    displayColor = saturate(lerp(luma.xxx, displayColor, 1.24) * 1.13 + 0.045);
                    albedo = ToLinear(displayColor);
                    float wrapped = pow(saturate(ndl * 0.5 + 0.5), 0.7);
                    float softShadow = lerp(0.68, 1.0, shadow);
                    float3 lightTint = lerp(float3(1,1,1), mainLight.color, 0.48);
                    color = albedo * (0.48 + wrapped * 0.72) * softShadow * lightTint;
                    color += pow(ndh, lerp(28.0, 90.0, gloss)) * gloss * mainLight.color * 0.30 * shadow;
                    color += float3(0.24,0.35,0.40) * pow(1.0 - noV, 3.0) * (0.04 + gloss * 0.06);
                    color *= lerp(0.88, 1.0, contact);
                }
                else if (_Style < 1.5)
                {
                    // Continuous URP BRDF, rough scratched metal, dry dust and fine surface relief.
                    float grime = Grime(input.positionOS, input.normalOS, _DetailScale);
                    float fineGrime = Grime(input.positionOS + float3(0.17,0.31,0.07), input.normalOS, _DetailScale * 4.1);
                    float flatSurfaceDetail = lerp(1.0, 0.15, ground);
                    float detail = max(_DetailStrength, 0.72) * flatSurfaceDetail;
                    float dust = (saturate((normalWS.y - 0.25) * 1.4) * 0.55 * _DustTop
                                + saturate(1.0 - input.positionWS.y * 0.7) * 0.65);
                    dust *= saturate(grime * 2.3 - 0.5) * max(_DustAmount, 0.32) * input.color.a * (1.0 - ground);
                    dust = saturate(dust);
                    float rust = smoothstep(0.64, 0.84, grime) * metal * (1.0 - ground) * 0.72;
                    float scratch = smoothstep(0.61, 0.81, fineGrime) * gloss * (1.0 - ground);
                    albedo *= lerp(1.0, 0.68 + grime * 0.58, detail);
                    albedo = lerp(albedo, float3(0.24,0.065,0.017), rust);
                    albedo = lerp(albedo, _DustColor.rgb, dust * 0.76);
                    albedo += scratch * metal * 0.035;
                    float height = ((grime - 0.5) * 0.014 + (fineGrime - 0.5) * 0.004) * flatSurfaceDetail;
                    // Road markings are albedo, not raised geometry. Using the road's color as
                    // height amplified triangle/UV derivatives into a distracting repeated pattern.
                    height += (dot(textureColor, float3(0.30,0.59,0.11)) - 0.5) * terrain * 0.002;
                    normalWS = DetailNormal(normalWS, input.positionWS, height);
                    noV = saturate(dot(normalWS, view));
                    float smoothness = lerp(0.16, 0.89, gloss);
                    smoothness = lerp(smoothness, 0.08, ground);
                    smoothness *= 1.0 - dust * 0.8;
                    smoothness *= 1.0 - rust * 0.65;
                    smoothness = saturate(smoothness + (fineGrime - 0.5) * 0.22 * flatSurfaceDetail - scratch * 0.20);

                    InputData lighting = (InputData)0;
                    lighting.positionWS = input.positionWS;
                    lighting.positionCS = input.positionCS;
                    lighting.normalWS = normalWS;
                    lighting.viewDirectionWS = view;
                    lighting.shadowCoord = shadowCoord;
                    lighting.fogCoord = 0;
                    lighting.vertexLighting = half3(0,0,0);
                    lighting.bakedGI = max(SampleSH(normalWS), half3(0.015,0.018,0.022));
                    lighting.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(input.positionCS);
                    lighting.shadowMask = half4(1,1,1,1);

                    SurfaceData surface = (SurfaceData)0;
                    surface.albedo = albedo;
                    surface.metallic = metal * (1.0 - rust) * (1.0 - dust);
                    surface.specular = half3(0.04,0.04,0.04);
                    surface.smoothness = smoothness;
                    surface.normalTS = half3(0,0,1);
                    surface.occlusion = contact;
                    surface.alpha = 1;
                    surface.clearCoatMask = gloss * (1.0 - metal) * (1.0 - dust) * 0.28;
                    surface.clearCoatSmoothness = 0.8;
                    color = UniversalFragmentPBR(lighting, surface).rgb;

                    // Procedural geometry disables reflection probes; use the game's existing environment instead.
                    // A continuous roughness-blurred reflection gives black paint/chrome volume without whitening albedo.
                    float3 f0 = lerp(float3(0.04,0.04,0.04), albedo, surface.metallic);
                    float3 fresnel = f0 + (1.0 - f0) * pow(1.0 - noV, 5.0);
                    float3 reflection = Environment(reflect(-view, normalWS), 1.0 - smoothness);
                    color += reflection * fresnel * (0.32 + smoothness * 0.65) * contact * (1.0 - dust * 0.65);
                }
                else if (_Style < 2.5)
                {
                    // Geometric face normals reveal planes, with flat clean palette and matte response.
                    float3 displayColor = ToDisplay(albedo);
                    displayColor = floor(saturate(displayColor * 1.10 + 0.035) * 7.0 + 0.5) / 7.0;
                    albedo = ToLinear(displayColor);
                    float light = saturate(ndl);
                    color = albedo * (0.36 + light * 0.92) * lerp(0.50, 1.0, shadow);
                    color *= lerp(float3(0.83,0.91,1.04), mainLight.color, light * 0.72);
                    color *= lerp(0.90, 1.0, contact);
                }
                else if (_Style < 3.5)
                {
                    // Three distinct light bands, dark ink contours and object-locked shadow hatching.
                    float3 displayColor = ToDisplay(albedo);
                    float luma = dot(displayColor, float3(0.299,0.587,0.114));
                    displayColor = saturate(lerp(luma.xxx, displayColor, 1.28) * 1.06 + 0.035);
                    displayColor = floor(displayColor * 6.0 + 0.5) / 6.0;
                    albedo = ToLinear(displayColor);
                    float lighting = ndl * lerp(0.15, 1.0, shadow);
                    float band = lighting < 0.06 ? 0.34 : (lighting < 0.53 ? 0.72 : 1.16);
                    float3 bandTint = lighting < 0.06 ? float3(0.64,0.78,0.91) : float3(1.04,0.98,0.87);
                    color = albedo * band * bandTint;
                    float3 p = input.positionOS;
                    float hatch = smoothstep(0.66, 0.94, sin((p.x + p.y * 0.7 + p.z) * 34.0));
                    float crossHatch = smoothstep(0.76, 0.96, sin((p.x - p.z + p.y * 0.5) * 29.0));
                    float dark = lighting < 0.20 ? 1.0 : 0.0;
                    color *= 1.0 - hatch * dark * 0.30 - crossHatch * dark * 0.15;
                    float specular = step(0.976, ndh) * step(0.08, lighting) * gloss;
                    color += specular * float3(0.62,0.69,0.67) * 0.6;
                }
                else
                {
                    // The root's point-upscaled low-res render makes real raster pixels; this pass supplies the palette.
                    float light = floor(saturate(ndl) * 3.0 + 0.5) / 3.0;
                    float shadowBand = shadow < 0.5 ? 0.55 : 1.0;
                    color = albedo * (0.37 + light * 0.96) * shadowBand;
                    color += step(0.985, ndh) * gloss * float3(0.20,0.22,0.18);
                }

                color += _Emission.rgb;
                // Keep lamps, goo and crystals self-lit through the original vertex-alpha convention.
                color = lerp(color, albedo * 1.6, saturate(1.0 - input.color.a));
                color = lerp(color, _FlashColor.rgb, saturate(_FlashColor.a));
                color = MixFog(color, input.fogFactor);
                if (_Style > 3.5) color = PixelPalette(color, input.positionCS.xy);
                return half4(max(color, 0.0), 1.0);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ComicOutline"
            Tags { "LightMode"="SRPDefaultUnlit" }
            Cull Front
            ZWrite Off

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex OutlineVertex
            #pragma fragment OutlineFragment
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            struct OutlineVaryings
            {
                float4 positionCS : SV_POSITION;
                float fogFactor : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            OutlineVaryings OutlineVertex(ArtAttributes input)
            {
                OutlineVaryings output = (OutlineVaryings)0;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);
                float3 normalOS = dot(input.outlineNormalOS, input.outlineNormalOS) > 0.01 ? input.outlineNormalOS : input.normalOS;
                float3 normalWS = TransformObjectToWorldNormal(normalOS);
                float4 positionCS = TransformObjectToHClip(input.positionOS.xyz);
                float2 direction = mul((float3x3)UNITY_MATRIX_VP, normalWS).xy;
                direction /= max(length(direction), 1e-4);
                float width = (_Style > 2.5 && _Style < 3.5) ? _OutlineWidth : 0.0;
                positionCS.xy += direction * (2.0 / max(_ScreenParams.xy, float2(1,1))) * width * positionCS.w;
                output.positionCS = positionCS;
                output.fogFactor = ComputeFogFactor(positionCS.z);
                return output;
            }

            half4 OutlineFragment(OutlineVaryings input) : SV_Target
            {
                // Zero-width hulls of other styles are discarded, including surfaces with coincident backfaces.
                clip((_Style > 2.5 && _Style < 3.5) ? 1.0 : -1.0);
                return half4(MixFog(_OutlineColor.rgb, input.fogFactor), 1.0);
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
            #pragma target 3.5
            #pragma vertex ShadowVertex
            #pragma fragment ShadowFragment
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;
            struct ShadowVaryings { float4 positionCS : SV_POSITION; };

            ShadowVaryings ShadowVertex(ArtAttributes input)
            {
                ShadowVaryings output;
                UNITY_SETUP_INSTANCE_ID(input);
                float3 positionWS = TransformObjectToWorld(input.positionOS.xyz);
                float3 normalWS = TransformObjectToWorldNormal(input.normalOS);
                #if defined(_CASTING_PUNCTUAL_LIGHT_SHADOW)
                    float3 lightDirection = normalize(_LightPosition - positionWS);
                #else
                    float3 lightDirection = _LightDirection;
                #endif
                float4 positionCS = TransformWorldToHClip(ApplyShadowBias(positionWS, normalWS, lightDirection));
                #if UNITY_REVERSED_Z
                    positionCS.z = min(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #else
                    positionCS.z = max(positionCS.z, UNITY_NEAR_CLIP_VALUE);
                #endif
                output.positionCS = positionCS;
                return output;
            }
            half4 ShadowFragment(ShadowVaryings input) : SV_Target { return 0; }
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
            #pragma target 3.5
            #pragma vertex ArtVertex
            #pragma fragment DepthFragment
            #pragma multi_compile_instancing
            half4 DepthFragment(ArtVaryings input) : SV_Target { return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode"="DepthNormalsOnly" }
            ZWrite On
            Cull Back

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex ArtVertex
            #pragma fragment NormalsFragment
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Packing.hlsl"

            half4 NormalsFragment(ArtVaryings input) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(input);
                float3 normalWS = normalize(input.normalWS);
                if (_Style > 1.5 && _Style < 2.5) normalWS = FacetNormal(input.positionWS, normalWS);
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
