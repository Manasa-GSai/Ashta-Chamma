import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#1a0a00',
    color: '#f5e6c8',
    fontFamily: "'Georgia', serif",
    padding: '2rem 1rem',
  },
  inner: {
    maxWidth: '720px',
    margin: '0 auto',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    marginBottom: '2rem',
  },
  title: {
    fontSize: '2rem',
    color: '#f5c842',
    margin: 0,
  },
  backButton: {
    background: 'transparent',
    border: '1px solid #555',
    color: '#aaa',
    padding: '0.4rem 1rem',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    flexShrink: 0,
  },
  section: {
    marginBottom: '2rem',
  },
  sectionTitle: {
    fontSize: '1.2rem',
    color: '#f5c842',
    marginTop: 0,
    marginBottom: '0.75rem',
    borderBottom: '1px solid #4a2800',
    paddingBottom: '0.4rem',
  },
  paragraph: {
    lineHeight: 1.7,
    margin: 0,
    color: '#ddd0b5',
  },
  rollList: {
    listStyle: 'none',
    padding: 0,
    margin: 0,
  },
  rollItem: {
    padding: '0.3rem 0',
    color: '#ddd0b5',
    lineHeight: 1.6,
  },
  rollItemHighlight: {
    color: '#f5c842',
    fontWeight: '600',
  },
} as const;

interface RollRowProps {
  label: string;
  highlight: boolean;
}

const RollRow = ({ label, highlight }: RollRowProps): JSX.Element => (
  <li style={styles.rollItem}>
    <span style={highlight ? styles.rollItemHighlight : undefined}>{label}</span>
  </li>
);

export const Rules = (): JSX.Element => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const rollValues: Array<{ key: string; highlight: boolean }> = [
    { key: 'rules.roll_0', highlight: true },
    { key: 'rules.roll_1', highlight: true },
    { key: 'rules.roll_2', highlight: false },
    { key: 'rules.roll_3', highlight: false },
    { key: 'rules.roll_4', highlight: true },
  ];

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        <header style={styles.header}>
          <button
            style={styles.backButton}
            onClick={() => void navigate('/')}
            type="button"
            aria-label={t('rules.back')}
          >
            ← {t('rules.back')}
          </button>
          <h1 style={styles.title}>{t('rules.title')}</h1>
        </header>

        <article>
          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t('rules.objective_title')}</h2>
            <p style={styles.paragraph}>{t('rules.objective_content')}</p>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t('rules.cowrie_title')}</h2>
            <p style={styles.paragraph}>{t('rules.cowrie_content')}</p>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t('rules.roll_values_title')}</h2>
            <ul style={styles.rollList}>
              {rollValues.map((row) => (
                <RollRow
                  key={row.key}
                  label={t(row.key)}
                  highlight={row.highlight}
                />
              ))}
            </ul>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t('rules.movement_title')}</h2>
            <p style={styles.paragraph}>{t('rules.movement_content')}</p>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>{t('rules.safe_squares_title')}</h2>
            <p style={styles.paragraph}>{t('rules.safe_squares_content')}</p>
          </section>
        </article>
      </div>
    </div>
  );
};
