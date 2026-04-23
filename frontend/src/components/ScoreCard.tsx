/**
 * ScoreCard — EAT-Lancet Alignment + Planetary Health scores.
 *
 * Shows two score panels side-by-side.  An expandable dimension breakdown
 * explains the individual 0–4 level per criterion.
 */

import { useState } from 'react';
import type { ScoreResponse } from '../api/types';

// ── Band helpers ──────────────────────────────────────────────────────────────

type Band = 'Strong' | 'Fair' | 'Mixed' | 'Weak';

function getBand(score: number): Band {
  if (score >= 80) return 'Strong';
  if (score >= 60) return 'Fair';
  if (score >= 40) return 'Mixed';
  return 'Weak';
}

const BAND_CLASS: Record<Band, string> = {
  Strong: 'score-band--strong',
  Fair:   'score-band--fair',
  Mixed:  'score-band--mixed',
  Weak:   'score-band--weak',
};

// ── Dimension labels ──────────────────────────────────────────────────────────

const DIM_LABELS: Record<string, string> = {
  plant_volume:      'Plant volume',
  whole_grains:      'Whole grains',
  legumes:           'Legumes',
  animal_moderation: 'Animal moderation',
  low_processing:    'Low processing',
  veg_diversity:     'Veg diversity',
  low_red_meat:      'Low red meat',
  fruit_nuts:        'Fruit & nuts',
};

// Which dimensions feed each score
const EAT_DIMS = ['plant_volume', 'whole_grains', 'legumes', 'animal_moderation', 'low_processing', 'veg_diversity'];
const PHD_DIMS = ['plant_volume', 'whole_grains', 'legumes', 'low_red_meat', 'low_processing', 'fruit_nuts'];

function DotBar({ level }: { level: number }) {
  return (
    <span className="score-dotbar" aria-label={`${level} out of 4`}>
      {[1, 2, 3, 4].map(i => (
        <span key={i} className={`score-dot${i <= level ? ' score-dot--filled' : ''}`} />
      ))}
    </span>
  );
}

function DimTable({
  dims,
  levels,
}: {
  dims: string[];
  levels: Record<string, number>;
}) {
  return (
    <table className="score-dim-table">
      <tbody>
        {dims.map(dim => (
          <tr key={dim}>
            <td className="score-dim-label">{DIM_LABELS[dim] ?? dim}</td>
            <td className="score-dim-dots"><DotBar level={levels[dim] ?? 0} /></td>
            <td className="score-dim-num">{levels[dim] ?? 0}/4</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Score panel ───────────────────────────────────────────────────────────────

function ScorePanel({
  label,
  score,
  dims,
  levels,
  showDetail,
}: {
  label: string;
  score: number;
  dims: string[];
  levels: Record<string, number>;
  showDetail: boolean;
}) {
  const band = getBand(score);
  return (
    <div className={`score-panel ${BAND_CLASS[band]}`}>
      <div className="score-panel-label">{label}</div>
      <div className="score-panel-number">{score.toFixed(1)}</div>
      <div className={`score-panel-band ${BAND_CLASS[band]}`}>{band}</div>
      <div className="score-panel-bar">
        <div className="score-panel-bar-fill" style={{ width: `${score}%` }} />
      </div>
      {showDetail && <DimTable dims={dims} levels={levels} />}
    </div>
  );
}

// ── Public component ──────────────────────────────────────────────────────────

interface Props {
  scores: ScoreResponse;
}

export default function ScoreCard({ scores }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="score-card">
      <div className="score-card-header">
        <span className="score-card-title">EAT-Lancet Scores</span>
        <button
          className="score-card-toggle"
          onClick={() => setExpanded(e => !e)}
          aria-expanded={expanded}
        >
          {expanded ? 'Hide breakdown ▲' : 'Show breakdown ▼'}
        </button>
      </div>

      <div className="score-panels">
        <ScorePanel
          label="EAT-Lancet Alignment"
          score={scores.eat_lancet}
          dims={EAT_DIMS}
          levels={scores.dimension_levels}
          showDetail={expanded}
        />
        <ScorePanel
          label="Planetary Health"
          score={scores.planetary_health}
          dims={PHD_DIMS}
          levels={scores.dimension_levels}
          showDetail={expanded}
        />
      </div>

      {expanded && (
        <p className="score-card-note">
          Scores 0–100. Bands: 80–100 Strong · 60–79 Fair · 40–59 Mixed · &lt;40 Weak.
          Based on Willett et al. (2019) EAT-Lancet Commission reference diet.
        </p>
      )}
    </div>
  );
}
