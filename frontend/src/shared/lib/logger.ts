type Level = "debug" | "info" | "warn" | "error";
type Sink = Pick<Console, Level>;
type Fields = Record<string, unknown>;
type Logger = Record<Level, (event: string, fields?: Fields) => void>;

const LEVELS: Level[] = ["debug", "info", "warn", "error"];

const plain = (value: unknown): unknown =>
  value instanceof Error
    ? { name: value.name, message: value.message, stack: value.stack }
    : value;

/** `debug`・`info`・`warn`・`error` を持ち、1 行の JSON をコンソールの同じレベルへ書くロガーを作る */
export const createLogger = (sink: Sink = console): Logger => {
  const write =
    (level: Level) =>
    (event: string, fields: Fields = {}) => {
      if (level === "debug" && import.meta.env.PROD) return;
      const entries = Object.entries(fields).map(([key, value]) => [
        key,
        plain(value),
      ]);
      sink[level](
        JSON.stringify({
          ts: new Date().toISOString(),
          level,
          event,
          ...Object.fromEntries(entries),
        }),
      );
    };
  return Object.fromEntries(
    LEVELS.map((level) => [level, write(level)]),
  ) as Logger;
};

export const logger = createLogger();
