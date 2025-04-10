module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.ts'], // Look for test files in the tests directory
  moduleFileExtensions: ['ts', 'js', 'json', 'node'],
  // Load environment variables before tests run
  setupFiles: ['dotenv/config'], // Simpler way to load .env directly 
  // setupFilesAfterEnv: ['./jest.setup.ts'], // Use this if more setup is needed
}; 