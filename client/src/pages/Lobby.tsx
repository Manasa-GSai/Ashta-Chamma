import { type FormEvent, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useGameStore } from '../store/gameStore';

interface AiPersona {
  id: string;
  name: string;
  difficulty_level: 'easy' | 'medium' | 'hard' | 'expert';
}

interface CreateRoomResponse {
  room_id: string;
  code: string;
}

interface JoinRoomResponse {
  player_index: number;
  color: string;
}

const ROOM_CODE_REGEX = /^[A-Za-z0-9]{6}$/;

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#1a0a00',
    color: '#f5e6c8',
    fontFamily: "'Georgia', serif",
    padding: '2rem 1rem',
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
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '2rem',
    maxWidth: '900px',
    margin: '0 auto',
  },
  card: {
    backgroundColor: '#2a1200',
    border: '1px solid #4a2800',
    borderRadius: '12px',
    padding: '1.5rem',
  },
  cardTitle: {
    fontSize: '1.4rem',
    color: '#f5c842',
    marginTop: 0,
    marginBottom: '1.5rem',
  },
  fieldset: {
    border: '1px solid #4a2800',
    borderRadius: '8px',
    padding: '0.75rem 1rem',
    marginBottom: '1rem',
  },
  legend: {
    color: '#c8a86a',
    fontSize: '0.9rem',
    padding: '0 0.25rem',
  },
  label: {
    display: 'block',
    marginBottom: '0.5rem',
    color: '#c8a86a',
    fontSize: '0.9rem',
  },
  select: {
    width: '100%',
    padding: '0.5rem',
    backgroundColor: '#1a0a00',
    border: '1px solid #4a2800',
    borderRadius: '6px',
    color: '#f5e6c8',
    fontSize: '1rem',
  },
  input: {
    width: '100%',
    padding: '0.5rem',
    backgroundColor: '#1a0a00',
    border: '1px solid #4a2800',
    borderRadius: '6px',
    color: '#f5e6c8',
    fontSize: '1rem',
    boxSizing: 'border-box' as const,
  },
  inputError: {
    borderColor: '#e05555',
  },
  errorText: {
    color: '#e05555',
    fontSize: '0.85rem',
    marginTop: '0.25rem',
    display: 'block',
  },
  submitButton: {
    width: '100%',
    padding: '0.75rem',
    backgroundColor: '#f5c842',
    color: '#1a0a00',
    border: 'none',
    borderRadius: '8px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '1rem',
  },
  submitButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginBottom: '0.4rem',
  },
  checkboxLabel: {
    color: '#f5e6c8',
    fontSize: '0.95rem',
    textTransform: 'capitalize' as const,
  },
  personaError: {
    color: '#e05555',
    fontSize: '0.85rem',
  },
  personaLoading: {
    color: '#888',
    fontSize: '0.85rem',
  },
} as const;

export const Lobby = (): JSX.Element => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setRoomCode } = useGameStore();

  // Create Room state
  const [maxPlayers, setMaxPlayers] = useState<number>(4);
  const [selectedPersonas, setSelectedPersonas] = useState<string[]>([]);
  const [personas, setPersonas] = useState<AiPersona[]>([]);
  const [personasLoading, setPersonasLoading] = useState<boolean>(true);
  const [personasError, setPersonasError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Join Room state
  const [joinCode, setJoinCode] = useState<string>('');
  const [codeError, setCodeError] = useState<string | null>(null);
  const [isJoining, setIsJoining] = useState<boolean>(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPersonas = async (): Promise<void> => {
      try {
        setPersonasLoading(true);
        setPersonasError(null);
        const data = await api.get<AiPersona[]>('/api/ai-personas');
        setPersonas(data);
      } catch {
        setPersonasError(t('common.error'));
      } finally {
        setPersonasLoading(false);
      }
    };

    void fetchPersonas();
  }, [t]);

  const handlePersonaToggle = (id: string): void => {
    setSelectedPersonas((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    );
  };

  const handleCreate = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setCreateError(null);
    setIsCreating(true);

    try {
      const body: { max_players: number; ai_personas?: string[] } = {
        max_players: maxPlayers,
      };
      if (selectedPersonas.length > 0) {
        body.ai_personas = selectedPersonas;
      }

      const data = await api.post<CreateRoomResponse>('/api/rooms', body);
      setRoomCode(data.code);
      void navigate(`/game/${data.code}`);
    } catch {
      setCreateError(t('common.error'));
    } finally {
      setIsCreating(false);
    }
  };

  const validateCode = (value: string): boolean => {
    if (!ROOM_CODE_REGEX.test(value)) {
      setCodeError(t('lobby.join.code_error'));
      return false;
    }
    setCodeError(null);
    return true;
  };

  const handleJoinCodeChange = (value: string): void => {
    const upper = value.toUpperCase();
    setJoinCode(upper);
    if (upper.length > 0) {
      validateCode(upper);
    } else {
      setCodeError(null);
    }
  };

  const handleJoin = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setJoinError(null);

    if (!validateCode(joinCode)) {
      return;
    }

    setIsJoining(true);

    try {
      await api.post<JoinRoomResponse>(
        `/api/rooms/${joinCode}/join`,
        {},
      );
      setRoomCode(joinCode);
      void navigate(`/game/${joinCode}`);
    } catch {
      setJoinError(t('common.error'));
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <button
          style={styles.backButton}
          onClick={() => void navigate('/')}
          type="button"
          aria-label={t('lobby.back')}
        >
          ← {t('lobby.back')}
        </button>
        <h1 style={styles.title}>{t('lobby.title')}</h1>
      </header>

      <div style={styles.grid}>
        {/* Create Room */}
        <section style={styles.card} aria-labelledby="create-room-heading">
          <h2 id="create-room-heading" style={styles.cardTitle}>
            {t('lobby.create.title')}
          </h2>

          <form onSubmit={(e) => void handleCreate(e)} noValidate>
            <label style={styles.label} htmlFor="max-players">
              {t('lobby.create.max_players')}
            </label>
            <select
              id="max-players"
              style={styles.select}
              value={maxPlayers}
              onChange={(e) => setMaxPlayers(Number(e.target.value))}
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
            </select>

            <fieldset style={{ ...styles.fieldset, marginTop: '1rem' }}>
              <legend style={styles.legend}>
                {t('lobby.create.ai_personas')}
              </legend>

              {personasLoading && (
                <p style={styles.personaLoading}>{t('common.loading')}</p>
              )}

              {personasError !== null && !personasLoading && (
                <p style={styles.personaError}>{personasError}</p>
              )}

              {!personasLoading &&
                personasError === null &&
                personas.map((persona) => (
                  <div key={persona.id} style={styles.checkboxRow}>
                    <input
                      type="checkbox"
                      id={`persona-${persona.id}`}
                      checked={selectedPersonas.includes(persona.id)}
                      onChange={() => handlePersonaToggle(persona.id)}
                    />
                    <label
                      htmlFor={`persona-${persona.id}`}
                      style={styles.checkboxLabel}
                    >
                      {persona.name} ({persona.difficulty_level})
                    </label>
                  </div>
                ))}

              {!personasLoading &&
                personasError === null &&
                personas.length === 0 && (
                  <p style={styles.personaLoading}>No AI personas available</p>
                )}
            </fieldset>

            {createError !== null && (
              <p role="alert" style={styles.errorText}>
                {createError}
              </p>
            )}

            <button
              type="submit"
              style={{
                ...styles.submitButton,
                ...(isCreating ? styles.submitButtonDisabled : {}),
              }}
              disabled={isCreating}
            >
              {isCreating ? t('lobby.create.loading') : t('lobby.create.submit')}
            </button>
          </form>
        </section>

        {/* Join Room */}
        <section style={styles.card} aria-labelledby="join-room-heading">
          <h2 id="join-room-heading" style={styles.cardTitle}>
            {t('lobby.join.title')}
          </h2>

          <form onSubmit={(e) => void handleJoin(e)} noValidate>
            <label style={styles.label} htmlFor="join-code">
              {t('lobby.join.code_label')}
            </label>
            <input
              id="join-code"
              type="text"
              style={{
                ...styles.input,
                ...(codeError !== null ? styles.inputError : {}),
              }}
              value={joinCode}
              onChange={(e) => handleJoinCodeChange(e.target.value)}
              placeholder={t('lobby.join.code_placeholder')}
              maxLength={6}
              autoComplete="off"
              aria-describedby={codeError !== null ? 'join-code-error' : undefined}
              aria-invalid={codeError !== null}
            />
            {codeError !== null && (
              <span id="join-code-error" role="alert" style={styles.errorText}>
                {codeError}
              </span>
            )}

            {joinError !== null && (
              <p role="alert" style={styles.errorText}>
                {joinError}
              </p>
            )}

            <button
              type="submit"
              style={{
                ...styles.submitButton,
                ...(isJoining ? styles.submitButtonDisabled : {}),
              }}
              disabled={isJoining}
            >
              {isJoining ? t('lobby.join.loading') : t('lobby.join.submit')}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
};
