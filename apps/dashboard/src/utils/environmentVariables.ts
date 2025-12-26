type DashboardEnvironment = {
  apiBaseUrl: string;
};

function readEnvVariable(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable "${name}" for dashboard runtime.`,
    );
  }
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(
      `Environment variable "${name}" must be a non-empty string.`,
    );
  }
  return trimmed;
}

export const environmentVariables: DashboardEnvironment = Object.freeze({
  apiBaseUrl: readEnvVariable("KANOMNOM_API_BASE_URL"),
});
