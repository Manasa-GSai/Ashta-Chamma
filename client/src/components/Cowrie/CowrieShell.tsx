import type { JSX } from 'react';
import * as THREE from 'three';

/**
 * Base sphere radius in Three.js world units (≈ 1.5 cm at 1 unit = 1 m scale).
 * The mesh is scaled to produce a realistic cowrie shell silhouette.
 */
const BASE_RADIUS = 0.15;

/**
 * Non-uniform scale factors applied to the base sphere to approximate a
 * Cypraea (cowrie) shell: elongated on X, flattened on Y, medium on Z.
 */
const SCALE_X = 1.2;
const SCALE_Y = 0.5;
const SCALE_Z = 0.8;

/** Derived half-height used for positioning ventral overlays. */
const HALF_HEIGHT = BASE_RADIUS * SCALE_Y; // 0.075

/**
 * CowrieShell renders the visual geometry of a single cowrie shell.
 *
 * The shell is oriented so its dome faces +Y and its flat ventral side faces -Y.
 * Visual state (mouth-up vs mouth-down) is therefore entirely determined by the
 * parent RigidBody's rotation — no props are needed. After physics settling, the
 * parent CowriePhysics component rotates the body to the server-determined
 * orientation, revealing either the cream ventral face or the brown dorsal dome.
 *
 * Geometry budget: all meshes are procedural Three.js geometry (zero KB of GLTF).
 */
export const CowrieShell = (): JSX.Element => {
  return (
    <group>
      {/*
       * Dorsal (dome) shell body — a sphere squished into an oval shape.
       * Brown/tan colouring matches the mottled dorsal pattern of a real cowrie.
       */}
      <mesh
        scale={[SCALE_X, SCALE_Y, SCALE_Z]}
        castShadow
        receiveShadow
      >
        <sphereGeometry args={[BASE_RADIUS, 24, 16]} />
        <meshStandardMaterial
          color="#9e6230"
          roughness={0.25}
          metalness={0.06}
          side={THREE.FrontSide}
        />
      </mesh>

      {/*
       * Ventral face — a cream/ivory oval disc sitting flush with the flat bottom.
       * Visible when the shell is mouth-up (flipped 180° around X).
       */}
      <mesh
        position={[0, -HALF_HEIGHT * 0.96, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        scale={[BASE_RADIUS * SCALE_X * 0.93, BASE_RADIUS * SCALE_Z * 0.93, 1]}
      >
        <circleGeometry args={[1, 24]} />
        <meshStandardMaterial
          color="#e8d5a8"
          roughness={0.45}
          metalness={0.0}
        />
      </mesh>

      {/*
       * Mouth slit — a dark elongated slot along the ventral face centreline.
       * The narrow width and contrasting colour recreate the toothed aperture.
       */}
      <mesh
        position={[0, -HALF_HEIGHT * 0.97, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <planeGeometry
          args={[BASE_RADIUS * SCALE_X * 1.6, BASE_RADIUS * SCALE_Z * 0.18]}
        />
        <meshStandardMaterial
          color="#1a0800"
          roughness={0.9}
          metalness={0.0}
        />
      </mesh>

      {/*
       * Dorsal ridge — a subtle dark stripe along the top centre of the shell
       * to suggest the characteristic pattern of Cypraea arabica.
       */}
      <mesh
        position={[0, HALF_HEIGHT * 0.5, 0]}
        rotation={[0, 0, 0]}
        scale={[SCALE_X * 0.15, SCALE_Y * 0.6, SCALE_Z * 0.12]}
      >
        <sphereGeometry args={[BASE_RADIUS, 12, 8]} />
        <meshStandardMaterial
          color="#5c3510"
          roughness={0.35}
          metalness={0.04}
        />
      </mesh>
    </group>
  );
};
