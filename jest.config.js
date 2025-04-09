module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.ts'], // Look for test files in the tests directory
  moduleFileExtensions: ['ts', 'js', 'json', 'node'],
  setupFilesAfterEnv: ['./jest.setup.ts'],
}; 