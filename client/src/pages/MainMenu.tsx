import { useClerk } from '@clerk/clerk-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: '#1a0a00',
    color: '#f5e6c8',
    fontFamily: "'Georgia', serif",
    padding: '1rem',
  },
  title: {
    fontSize: 'clamp(2.5rem, 8vw, 5rem)',
    fontWeight: 'bold',
    marginBottom: '0.5rem',
    textAlign: 'center' as const,
    color: '#f5c842',
    textShadow: '0 2px 8px rgba(245, 200, 66, 0.4)',
  },
  subtitle: {
    fontSize: 'clamp(0.9rem, 2.5vw, 1.2rem)',
    marginBottom: '3rem',
    opacity: 0.7,
    textAlign: 'center' as const,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '1rem',
    width: '100%',
    maxWidth: '280px',
  },
  button: {
    padding: '0.85rem 2rem',
    fontSize: '1.1rem',
    fontWeight: '600',
    border: '2px solid #f5c842',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'background-color 0.2s, color 0.2s',
    width: '100%',
  },
  primaryButton: {
    backgroundColor: '#f5c842',
    color: '#1a0a00',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    color: '#f5c842',
  },
  signOutButton: {
    backgroundColor: 'transparent',
    color: '#aaa',
    borderColor: '#555',
    fontSize: '0.95rem',
  },
} as const;

export const MainMenu = (): JSX.Element => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  // useClerk may not be available if ClerkProvider is not configured —
  // we guard against that with a try/catch at call time.
  const clerk = useClerk();

  const handlePlay = (): void => {
    void navigate('/lobby');
  };

  const handleRules = (): void => {
    void navigate('/rules');
  };

  const handleSignOut = (): void => {
    void clerk.signOut();
  };

  return (
    <main style={styles.container}>
      <h1 style={styles.title}>{t('main_menu.title')}</h1>
      <p style={styles.subtitle}>{t('main_menu.subtitle')}</p>

      <nav aria-label="Main navigation" style={styles.nav}>
        <button
          style={{ ...styles.button, ...styles.primaryButton }}
          onClick={handlePlay}
          type="button"
        >
          {t('main_menu.play')}
        </button>

        <button
          style={{ ...styles.button, ...styles.secondaryButton }}
          onClick={handleRules}
          type="button"
        >
          {t('main_menu.rules')}
        </button>

        <button
          style={{ ...styles.button, ...styles.signOutButton }}
          onClick={handleSignOut}
          type="button"
        >
          {t('main_menu.sign_out')}
        </button>
      </nav>
    </main>
  );
};
