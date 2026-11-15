import { Share } from 'react-native';

import type { Game, HotColdBoard } from '@/api/types';
import { formatDay, lang } from '@/i18n';

const SQUARES: Record<string, string> = { hit: '🟩', close: '🟨', miss: '⬛', info: '⬜' };

/** Résultat partageable, sans rien dévoiler du vin (à la Wordle). */
export function shareBlindtest(game: Game) {
  const grid = game.guesses.filter((g) => g.counted).map((g) => SQUARES[g.verdict]).join('');
  const when = game.mode === 'daily' && game.day ? formatDay(game.day) : lang === 'fr' ? 'partie libre' : 'free game';
  const head = lang === 'fr' ? `Wine Explorer · Blind test (${when})` : `Wine Explorer · Blind test (${when})`;
  const result = game.status === 'won'
    ? (lang === 'fr' ? `Trouvé en ${game.attempts_used}/${game.max_attempts} · ${game.score} pts` : `Solved in ${game.attempts_used}/${game.max_attempts} · ${game.score} pts`)
    : `${game.status_label} · ${game.score} pts`;
  return Share.share({ message: `${head}\n${result}\n${grid}` });
}

export function shareHotcold(board: HotColdBoard) {
  const when = board.mode === 'daily' ? formatDay(board.day) : lang === 'fr' ? 'partie libre' : 'free game';
  const head = `Wine Explorer · ${lang === 'fr' ? 'Chaud-froid' : 'Hot & cold'} (${when})`;
  const path = [...board.rows].sort((a, b) => (a.n ?? 0) - (b.n ?? 0)).map((r) => r.emoji).join('');
  const result = board.over === 'won'
    ? (lang === 'fr' ? `Trouvé en ${board.count} proposition${board.count > 1 ? 's' : ''}` : `Found in ${board.count} guess${board.count > 1 ? 'es' : ''}`)
    : (lang === 'fr' ? 'Abandonné' : 'Gave up');
  return Share.share({ message: `${head}\n${result}\n${path}` });
}
