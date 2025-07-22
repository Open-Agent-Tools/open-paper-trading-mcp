# Contributing to Open Paper Trading MCP

First off, thank you for considering contributing! This project is an open-source effort, and we welcome any and all contributions.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

We recommend a "forking workflow" for all contributions.

### 1. Fork the Repository

Start by forking the main repository to your own GitHub account.

### 2. Clone Your Fork

Clone your forked repository to your local machine:

```bash
git clone https://github.com/yourusername/open-paper-trading-mcp.git
cd open-paper-trading-mcp
```

### 3. Create a Branch

Create a new branch for your feature or bug fix. Please use a descriptive name that follows our branching strategy.

#### Branching Strategy

-   **Features:** `feature/<descriptive-name>` (e.g., `feature/add-trailing-stop-orders`)
-   **Bug Fixes:** `fix/<descriptive-name>` (e.g., `fix/resolve-order-cancellation-bug`)
-   **Documentation:** `docs/<descriptive-name>` (e.g., `docs/update-readme-configuration`)

```bash
git checkout -b feature/your-amazing-feature
```

### 4. Make Your Changes

Make your changes to the codebase. Ensure that your code follows the existing style and conventions.

### 5. Run Quality Checks

Before committing, run the full suite of quality checks to ensure your changes meet our standards. This includes formatting, linting, type checking, and running the test suite.

```bash
python scripts/dev.py check
```

All checks must pass before your contribution can be merged.

### 6. Commit Your Changes

Commit your changes with a clear and descriptive commit message. We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.

**Format:** `<type>[optional scope]: <description>`

-   **`feat`:** A new feature
-   **`fix`:** A bug fix
-   **`docs`:** Documentation only changes
-   **`style`:** Changes that do not affect the meaning of the code (white-space, formatting, etc.)
-   **`refactor`:** A code change that neither fixes a bug nor adds a feature
-   **`test`:** Adding missing tests or correcting existing tests
-   **`chore`:** Changes to the build process or auxiliary tools

**Example:**

```bash
git commit -m "feat: Add support for stop-loss orders"
```

### 7. Push to Your Fork

Push your changes to your forked repository:

```bash
git push origin feature/your-amazing-feature
```

### 8. Open a Pull Request

Open a pull request from your forked repository to the `main` branch of the original repository. Provide a clear description of your changes and reference any related issues.

Thank you for your contribution!
