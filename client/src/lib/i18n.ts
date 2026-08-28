/**
 * Minimal i18n utility providing a t() translation function.
 * All UI strings are keyed here so they can be migrated to a full i18next
 * setup without changing call-sites when translations are added.
 */

const en: Record<string, string> = {
  // Common
  'common.loading': 'Loading…',
  'common.error.title': 'Something went wrong',
  'common.error.retry': 'Retry',
  'common.nav.home': 'Home',
  'common.nav.leaderboard': 'Leaderboard',
  'common.nav.profile': 'Profile',

  // Leaderboard page
  'leaderboard.title': 'Leaderboard',
  'leaderboard.filter.week': 'Week',
  'leaderboard.filter.month': 'Month',
  'leaderboard.filter.all': 'All Time',
  'leaderboard.table.rank': 'Rank',
  'leaderboard.table.player': 'Player',
  'leaderboard.table.wins': 'Wins',
  'leaderboard.table.games': 'Games',
  'leaderboard.table.winRate': 'Win Rate',
  'leaderboard.empty': 'No scores yet. Be the first to play!',
  'leaderboard.you': '(You)',

  // Profile / score history page
  'profile.title': 'My Profile',
  'profile.history.title': 'Game History',
  'profile.history.date': 'Date',
  'profile.history.result': 'Result',
  'profile.history.duration': 'Duration',
  'profile.history.captured': 'Pawns Captured',
  'profile.history.empty': 'No games played yet.',
  'profile.result.win': 'Win',
  'profile.result.loss': 'Loss',
  'profile.error.auth': 'Please log in to view your profile.',
};

/**
 * Returns the translated string for `key`, falling back to the key itself.
 * Supports `{{placeholder}}` substitution via the `substitutions` map.
 */
export function t(key: string, substitutions?: Record<string, string>): string {
  let value = en[key] ?? key;
  if (substitutions !== undefined) {
    for (const [k, v] of Object.entries(substitutions)) {
      value = value.replace(`{{${k}}}`, v);
    }
  }
  return value;
}
