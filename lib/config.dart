class Config {
  // Default to localhost — override per device in Settings.
  static const String apiBase = 'http://127.0.0.1:8000';

  // Server-side shared secret; pair with the same value in server/.env.
  static const String apiKey = 'hermes-dev-key-change-me';
}
