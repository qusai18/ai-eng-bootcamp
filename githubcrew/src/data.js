export const PATCH = {
  scout: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="7"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/></svg>`,
  cartographer: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3h18v18H3z"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18" opacity=".4"/><path d="M5 19l6-6 3 2 5-8" stroke-width="1.8"/><circle cx="5" cy="19" r="1.4" fill="currentColor" stroke="none"/><circle cx="19" cy="7" r="1.4" fill="currentColor" stroke="none"/></svg>`,
  pulse: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M1 12h4l3-8 5 16 3-8h7"/></svg>`,
  archivist: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 2h9l5 5v15H6z"/><path d="M15 2v5h5"/><path d="M9 12h8M9 16h8M9 8h3"/></svg>`,
  guard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2l8 3v6c0 5-3.5 9.3-8 11-4.5-1.7-8-6-8-11V5z"/><path d="M5.5 10.5h13" stroke-width="1.2" opacity=".55"/><circle cx="9" cy="10.5" r="1.3" fill="currentColor" stroke="none"/><circle cx="15" cy="10.5" r="1.3" fill="currentColor" stroke="none"/></svg>`,
  warden: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 2l8 3v6c0 5-3.5 9.3-8 11-4.5-1.7-8-6-8-11V5z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>`,
};

export const AGENTS = [
  { id: 'scout', name: 'SCOUT', role: 'Reconnaissance', line: 'Verifies the target and pulls its vitals — stars, forks, license, age.' },
  { id: 'cartographer', name: 'CARTOGRAPHER', role: 'Structural survey', line: 'Maps languages, root artifacts, CI pipelines and test suites.' },
  { id: 'pulse', name: 'PULSE', role: 'Activity & cadence', line: 'Reads the last hundred commits and finds the heartbeat.' },
  { id: 'archivist', name: 'ARCHIVIST', role: 'Documentation audit', line: 'Grades the README and the auxiliary paperwork.' },
  { id: 'guard', name: 'GUARD', role: 'Security & compliance', line: 'Maps security controls against NIST RMF and screens for EU AI Act exposure.' },
  { id: 'warden', name: 'WARDEN', role: 'Synthesis & verdict', line: 'Weighs every finding, then signs the dossier.' },
];

export const AGMAP = Object.fromEntries(AGENTS.map((a) => [a.id, a]));

export const EXAMPLES = ['sindresorhus/is', 'ollama/ollama', 'encode/httpx'];

export const STACKMAP = [
  ['package.json', 'Node.js'], ['deno.json', 'Deno'], ['bun.lockb', 'Bun'],
  ['requirements.txt', 'Python'], ['pyproject.toml', 'Python'], ['Pipfile', 'Python'], ['setup.py', 'Python'],
  ['go.mod', 'Go'], ['Cargo.toml', 'Rust'], ['pom.xml', 'Java (Maven)'], ['build.gradle', 'Java (Gradle)'],
  ['composer.json', 'PHP'], ['Gemfile', 'Ruby'], ['*.csproj', '.NET'], ['mix.exs', 'Elixir'],
  ['Dockerfile', 'Docker'], ['docker-compose.yml', 'Docker Compose'], ['Makefile', 'Make'], ['CMakeLists.txt', 'CMake'],
  ['pubspec.yaml', 'Flutter/Dart'], ['Package.swift', 'Swift'], ['flake.nix', 'Nix'],
];

export const KNOWN = new Set(['feat', 'fix', 'chore', 'docs', 'refactor', 'test', 'ci', 'perf', 'build', 'style', 'revert', 'merge']);
export const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

export const SEC_WF = /codeql|security|scan|snyk|trivy|semgrep|bandit|audit|anchore|grype|zap/i;
export const SENSITIVE = ['password', 'secret', 'credential', 'token', 'authentication', 'oauth', 'encryption', 'cryptography', 'personal data', 'pii', 'privacy', 'health', 'medical', 'payment', 'financial', 'biometric'];
export const AI_SIGNALS = ['machine learning', 'deep learning', 'neural network', 'artificial intelligence', ' llm', 'language model', 'large language', ' gpt', 'transformer', 'diffusion model', 'inference', 'training data', 'computer vision', 'natural language', 'chatbot', 'conversational ai', 'ai agent', 'agent framework', 'autonomous agent', 'reinforcement learning', 'embedding', 'text generation', 'image generation', 'speech recognition'];
export const AI_PROHIBITED = ['social scoring', 'emotion recognition', 'biometric categorisation', 'biometric categorization', 'real-time biometric', 'remote biometric identification'];
export const AI_HIGH = ['biometric', 'facial recognition', 'emotion', 'credit scoring', 'creditworthiness', 'recruitment', 'hiring', 'applicant', 'resume screening', 'cv screening', 'loan approval', 'insurance pricing', 'proctoring', 'medical diagnosis', 'diagnostic', 'patient triage', 'critical infrastructure', 'law enforcement', 'border control', 'migration', 'asylum', 'essential services'];

export function demoPayload() {
  const now = new Date().toISOString();
  return {
    repo: 'demo/field-notes',
    demo: true,
    meta: {
      name: 'field-notes',
      owner: { login: 'demo' },
      description: 'An illustrative team knowledge base with a typed API and automated checks.',
      stargazers_count: 1280,
      forks_count: 84,
      open_issues_count: 12,
      created_at: '2023-03-01T00:00:00Z',
      pushed_at: now,
      language: 'TypeScript',
      license: { spdx_id: 'MIT' },
      default_branch: 'main',
      topics: ['knowledge-base'],
      archived: false,
    },
    langs: { TypeScript: 82000, CSS: 12000, HTML: 6000 },
    root: ['package.json', 'README.md', 'LICENSE', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'Dockerfile']
      .map((name) => ({ name, type: 'file' }))
      .concat([{ name: 'tests', type: 'dir' }]),
    wf: ['ci.yml', 'codeql.yml'],
    ghDot: [{ name: 'dependabot.yml' }, { name: 'CODEOWNERS' }],
    release: { tag: 'v1.4.0', at: now },
    readme: '# Field Notes\nA team knowledge base.\n## Installation\nnpm install\n## Usage\nnpm start\n## API\nSee reference docs.\n## Testing\nnpm test\n## Contributing\nPull requests welcome.\n## License\nMIT',
    commits: Array.from({ length: 48 }, (_, i) => ({
      commit: {
        author: { date: new Date(Date.now() - i * 86400000).toISOString(), name: 'Demo contributor' },
        message: i % 3 ? 'feat: improve notes search' : 'fix: keyboard navigation',
      },
      author: { login: 'demo-contributor' },
    })),
    contribs: [
      { login: 'alex-demo', contributions: 120 },
      { login: 'sam-demo', contributions: 75 },
      { login: 'jules-demo', contributions: 42 },
    ],
  };
}
