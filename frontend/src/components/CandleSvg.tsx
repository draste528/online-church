import React from 'react';

interface CandleSvgProps {
  lit: boolean;
  /** Height of the wax body in SVG units; the flame and wick follow the top of the wax. */
  waxHeight: number;
}

const BASE_Y = 182; // bottom edge of the wax body
const FLAME_OUTER =
  'M0 -42 C7 -29 15 -20 15 -10 C15 -2 8 3 0 3 C-8 3 -15 -2 -15 -10 C-15 -20 -7 -29 0 -42 Z';
const FLAME_INNER = 'M0 -26 C4 -20 8 -15 8 -9 C8 -4 4 0 0 0 C-4 0 -8 -4 -8 -9 C-8 -15 -4 -20 0 -26 Z';

/** Pure SVG candle: wax with a rounded top, a wick, a dashed flame outline when out, an animated flame when lit. */
export const CandleSvg: React.FC<CandleSvgProps> = ({ lit, waxHeight }) => {
  const top = BASE_Y - waxHeight;
  return (
    <svg
      className={lit ? 'candle-svg lit' : 'candle-svg'}
      viewBox="0 0 120 200"
      role="presentation"
      focusable="false"
    >
      <defs>
        <linearGradient id="candle-wax" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#f3dfa6" />
          <stop offset="0.35" stopColor="#fdf3d2" />
          <stop offset="1" stopColor="#e0c27a" />
        </linearGradient>
        <linearGradient id="candle-brass" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="#9a7728" />
          <stop offset="0.45" stopColor="#e2c06b" />
          <stop offset="1" stopColor="#8a6a22" />
        </linearGradient>
        <linearGradient id="candle-flame" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#f08a1a" />
          <stop offset="0.55" stopColor="#f8c13c" />
          <stop offset="1" stopColor="#fff1ae" />
        </linearGradient>
        <linearGradient id="candle-flame-core" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#ffe9a0" />
          <stop offset="1" stopColor="#fffbe8" />
        </linearGradient>
        <radialGradient id="candle-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ffc857" stopOpacity="0.6" />
          <stop offset="0.5" stopColor="#ffc857" stopOpacity="0.2" />
          <stop offset="1" stopColor="#ffc857" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Holder */}
      <ellipse cx="60" cy="189" rx="38" ry="7" fill="url(#candle-brass)" />
      <ellipse cx="60" cy="186" rx="31" ry="5" fill="#f0d68a" opacity="0.85" />

      {/* Wax body with rounded shoulders, melted pool on top and a drip */}
      <path
        d={`M40 ${BASE_Y} V${top + 12} Q40 ${top} 52 ${top} H68 Q80 ${top} 80 ${top + 12} V${BASE_Y} Q60 ${BASE_Y + 6} 40 ${BASE_Y} Z`}
        fill="url(#candle-wax)"
        stroke="#d9bd7c"
        strokeWidth="1"
      />
      <ellipse cx="60" cy={top + 2} rx="15" ry="3.5" fill="#fff8dc" opacity="0.9" />
      <path
        d={`M71 ${top + 5} v${Math.min(26, waxHeight - 16)} q0 5 3.2 0 v-${Math.min(26, waxHeight - 16)} z`}
        fill="#fff4cf"
        stroke="#e6cf93"
        strokeWidth="0.6"
      />
      <path d={`M46 ${top + 10} V${BASE_Y - 6}`} stroke="#fff" strokeWidth="2" strokeLinecap="round" opacity="0.45" />

      {/* Wick, flame and glow share one origin: the tip of the wick */}
      <g transform={`translate(60 ${top - 10})`}>
        <circle className="candle-glow" cx="0" cy="-18" r="46" fill="url(#candle-glow)" />
        <path
          d={`M0 ${10} Q-1 4 1 -2`}
          transform="translate(0 0)"
          stroke="#3a2d28"
          strokeWidth="2.4"
          fill="none"
          strokeLinecap="round"
        />
        <path className="flame-outline" d={FLAME_OUTER} fill="none" stroke="#b8913a" strokeWidth="1.4" strokeDasharray="3 3" />
        <g className="flame">
          <path className="flame-outer" d={FLAME_OUTER} fill="url(#candle-flame)" />
          <path className="flame-inner" d={FLAME_INNER} fill="url(#candle-flame-core)" />
          <ellipse cx="0" cy="-2" rx="3.4" ry="4.6" fill="#6f9bff" opacity="0.55" />
        </g>
      </g>
    </svg>
  );
};
