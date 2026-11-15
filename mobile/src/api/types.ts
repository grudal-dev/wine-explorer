export type WineBrief = { slug: string; name: string; color: string; color_label: string };

export type User = { username: string; email: string; date_joined: string };

export type Aroma = { name: string; intensity: number; family: string; hue: string };

export type Slot = { key: string; label: string; found: boolean; answer: string | null };

export type Guess = {
  label: string;
  kind: string;
  verdict: 'hit' | 'close' | 'miss' | 'info';
  verdict_label: string;
  feedback: string;
  counted: boolean;
};

export type Game = {
  id: string;
  mode: 'daily' | 'free';
  mode_label: string;
  day: string | null;
  status: 'playing' | 'won' | 'lost' | 'abandoned';
  status_label: string;
  is_over: boolean;
  is_owner: boolean;
  score: number;
  attempts_used: number;
  attempts_left: number;
  max_attempts: number;
  player: string | null;
  sheet: {
    color: string;
    color_label: string;
    style: string;
    structure: { label: string; value: number }[];
    aromas: Aroma[];
    aromas_hidden: number;
    clues: { key: string; title: string; body: string }[];
    next_clue: string | null;
    slots: Slot[];
    minor_grapes: string[];
  };
  guesses: Guess[];
  wine: WineBrief | null;
};

export type GameRow = {
  id: string;
  mode: 'daily' | 'free';
  mode_label: string;
  status: Game['status'];
  status_label: string;
  score: number;
  created_at: string;
  wine: WineBrief | null;
};

export type HotColdRow = {
  id: string;
  label: string;
  type: string;
  type_label: string;
  temperature: number;
  rank: number;
  emoji: string;
  band: string;
  found: boolean;
  gauge: number;
  n?: number;
  guessed?: boolean;
  wine?: string;
};

export type HotColdBoard = {
  mode: 'daily' | 'free';
  day: string;
  ranked: { score: number; guesses: number } | null;
  rows: HotColdRow[];
  last: HotColdRow | null;
  best: HotColdRow | null;
  count: number;
  over: '' | 'won' | 'abandoned';
  top: number;
  total: number;
  answer?: { id: string; label: string; wine?: string };
  closest?: HotColdRow[];
};

export type HotColdHistory = {
  day: string;
  outcome: 'won' | 'abandoned';
  outcome_label: string;
  guesses: number;
  score: number;
  wine: WineBrief | null;
};

export type Stats = {
  played: number;
  won: number;
  rate: number;
  avg: number;
  regions: { name: string; played: number; won: number; rate: number }[];
};

export type Today = {
  day: string;
  seconds_left: number;
  blindtest: { state: 'todo' | 'playing' | 'done'; game_id: string | null; score: number | null; status_label: string | null };
  hotcold: { state: 'todo' | 'playing' | 'done'; guesses: number; score: number | null };
  colors: { key: string; label: string }[];
};

export type RankingRow = {
  username: string;
  points: number;
  played: number;
  wins: number;
  blindtest?: number;
  hotcold?: number;
  result?: string;
  best?: number;
  guesses?: number;
};

export type Rankings = { game: 'total' | 'blindtest' | 'hotcold'; day: string; today: RankingRow[]; all_time: RankingRow[] };

export type Player = {
  username: string;
  is_self: boolean;
  stats: Stats;
  games: GameRow[];
  hotcold: HotColdHistory[];
};

export type Me = { user: User; stats: Stats; games: GameRow[]; hotcold: HotColdHistory[] };

export type Suggestion = { key: string; label: string; hint: string; choice: string };

export type Wine = WineBrief & {
  style: string;
  appellation: string;
  region: string;
  subregion: string | null;
  grapes: { name: string; share: number }[];
  aromas: Aroma[];
  structure: { label: string; value: number }[];
  description: string;
  pairings: string[];
  price_min: number | null;
  price_max: number | null;
  aging_min: number | null;
  aging_max: number | null;
  serving_temp: string;
};
