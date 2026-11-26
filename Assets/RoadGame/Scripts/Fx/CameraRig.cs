using UnityEngine;

namespace RoadGame
{
    /// <summary>Top-down 3/4 follow camera (portrait). Keeps a fixed visible ground width so the car always has room.</summary>
    public class CameraRig : MonoBehaviour
    {
        public Camera cam;
        public Transform target;
        public float pitch = 54f;
        public float fov = 46f;
        public float halfWidth = 13.5f;     // meters visible left/right of the car (portrait)
        public float minHalfHeight = 18.5f; // for landscape screens: about the ground area a portrait phone shows (was 15: half its height)
        public float zoom = 1f;

        Vector3 focus;
        Vector3 focusVel;
        Vector3 lookAhead;
        float shake;
        float distance;

        public static CameraRig Create(Camera cam, Transform target)
        {
            var rig = cam.gameObject.AddComponent<CameraRig>();
            rig.cam = cam;
            rig.target = target;
            cam.fieldOfView = rig.fov;
            cam.nearClipPlane = 1f;
            cam.farClipPlane = 190f;
            rig.focus = target.position;
            rig.Snap();
            return rig;
        }

        public void Shake(float amount) { shake = Mathf.Max(shake, amount); }

        float ComputeDistance()
        {
            float aspect = Mathf.Max(0.3f, cam.aspect);
            float t = Mathf.Tan(fov * 0.5f * Mathf.Deg2Rad);
            float dW = halfWidth / (t * aspect);
            float dH = minHalfHeight / t;
            return Mathf.Max(dW, dH) * zoom;
        }

        public void Snap()
        {
            if (target == null) return;
            focus = target.position;
            var pl = Game.I != null ? Game.I.player : null;
            if (pl != null && target == pl.transform) focus.y = pl.CameraY;
            focusVel = Vector3.zero;
            lookAhead = Vector3.zero;
            distance = ComputeDistance();
            Apply(0f);
        }

        void LateUpdate()
        {
            if (target == null) return;
            float dt = Time.deltaTime;
            var player = Game.I != null ? Game.I.player : null;
            Vector3 vel = player != null ? player.Velocity : Vector3.zero;
            lookAhead = Vector3.Lerp(lookAhead, vel * 0.32f, 1f - Mathf.Exp(-2.5f * dt));
            var goal = target.position + lookAhead + new Vector3(0, 0, 2.5f);
            // vertical: follow the floor the car is on (tunnels, ramps) smoothly, only a little of a jump's height
            if (player != null && target == player.transform) goal.y = player.CameraY;
            focus = Vector3.SmoothDamp(focus, goal, ref focusVel, 0.12f, 200f, dt);
            distance = Mathf.Lerp(distance, ComputeDistance(), 1f - Mathf.Exp(-4f * dt));
            Apply(dt);
        }

        void Apply(float dt)
        {
            var rot = Quaternion.Euler(pitch, 0, 0);
            var pos = focus - rot * Vector3.forward * distance;
            if (shake > 0f && !(Game.I != null && Game.I.paused))
            {
                // real time: a hit-stop or the Dev speed neither freezes the camera off centre nor stretches the shake;
                // a paused game (menus) shows a still picture
                if (dt > 0f) shake = Mathf.MoveTowards(shake, 0, Time.unscaledDeltaTime * 2.2f);
                float s = shake * shake * 0.9f;
                float tt = Time.unscaledTime * 30f;
                pos += new Vector3(Mathf.PerlinNoise(tt, 0.1f) - 0.5f, Mathf.PerlinNoise(0.2f, tt) - 0.5f, 0) * s * 2f;
            }
            transform.SetPositionAndRotation(pos, rot);
        }
    }
}
