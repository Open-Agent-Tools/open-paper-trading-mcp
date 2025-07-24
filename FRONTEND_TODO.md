# Frontend Development TODO

This document outlines the development plan for the React-based web frontend. The plan is divided into prioritized, dependency-ordered phases, with each phase containing clear, vertically-sliced tasks.

---

## Phase 1: Project Setup & Foundational Integration ✅ 

**Status: COMPLETED**
**Goal**: Establish the frontend project, containerize it, and ensure basic communication with the backend API. This phase is the foundation for all subsequent development.

-   [x] **Task 1.1: Scaffold Frontend Application**
    -   **Action**: Create a `frontend` directory at the project root.
    -   **Action**: Inside `frontend/`, use `uv run npm create vite@latest -- --template react-ts` to initialize a new React application with TypeScript.
    -   **Verification**: The default Vite React app runs successfully locally via `npm run dev`.

-   [x] **Task 1.2: Dockerize the Frontend**
    -   **Dependency**: Task 1.1
    -   **Action**: Create a multi-stage `frontend/Dockerfile`.
        -   Stage 1: Use a `node` image to build the static assets (`npm run build`).
        -   Stage 2: Use a lightweight `nginx` image to serve the built assets from Stage 1.
    -   **Action**: Create a `frontend/.dockerignore` file to exclude `node_modules` and other unnecessary files from the Docker context.
    -   **Verification**: The frontend Docker image builds successfully.

-   [x] **Task 1.3: Integrate with Docker Compose**
    -   **Dependency**: Task 1.2
    -   **Action**: Add a new `frontend` service to the main `docker-compose.yml` file.
    -   **Action**: Configure the service to build from `frontend/Dockerfile`, expose port `3000`, and set `depends_on: [app]`.
    -   **Verification**: Running `docker-compose up` starts the backend, database, and the new frontend service successfully. The frontend is accessible in the browser at `http://localhost:3000`.

-   [x] **Task 1.4: Enable Backend Communication (CORS)**
    -   **Dependency**: Task 1.3
    -   **Action**: Modify `app/main.py` to include FastAPI's `CORSMiddleware`.
    -   **Action**: Configure the middleware to allow requests from the frontend's origin (`http://localhost:3000`).
    -   **Verification**: A test API call from the frontend app (e.g., using `fetch` in a `useEffect` hook) to a backend endpoint (like `/api/v1/health`) succeeds without CORS errors in the browser console.

---

## Phase 2: Core UI Layout & Components ✅ 

**Status: COMPLETED**
**Goal**: Build the main application shell, integrate the UI component library, and set up navigation.

-   [x] **Task 2.1: Install Core UI Libraries**
    -   **Dependency**: Phase 1
    -   **Action**: In the `frontend` directory, install Material-UI (MUI) and its dependencies: `@mui/material`, `@emotion/react`, `@emotion/styled`.
    -   **Action**: Install `react-router-dom` for client-side routing.
    -   **Action**: Install `axios` for making API requests.
    -   **Verification**: All dependencies are added to `package.json` and the application still runs.

-   [x] **Task 2.2: Implement Main Application Layout**
    -   **Dependency**: Task 2.1
    -   **Action**: Create a main layout component (`components/Layout.tsx`) that includes a persistent header/navigation bar and a main content area.
    -   **Action**: Use MUI components like `AppBar`, `Toolbar`, `Container`, and `Box` to structure the page.
    -   **Verification**: The main layout renders correctly with a header and a content area.

-   [x] **Task 2.3: Set Up Client-Side Routing**
    -   **Dependency**: Task 2.2
    -   **Action**: Configure `react-router-dom` in `App.tsx` to manage different pages.
    -   **Action**: Create placeholder page components for key views: `Dashboard`, `Account`, `Orders`.
    -   **Action**: Add navigation links to the `AppBar` in the `Layout` component to switch between these views.
    -   **Verification**: Clicking navigation links correctly renders the corresponding placeholder page component without a full page reload.

---

## Phase 3: Account & Portfolio Data Display ✅

**Status: COMPLETED**
**Goal**: Fetch and display essential account and portfolio information, bringing the dashboard to life with real data from the backend.

-   [x] **Task 3.1: Create a Centralized API Client**
    -   **Dependency**: Task 2.1
    -   **Action**: Create a `services/apiClient.ts` module.
    -   **Action**: Configure an `axios` instance with the base URL for the backend API (`http://localhost:2080/api/v1`).
    -   **Action**: Add functions for each backend endpoint required in this phase (`getAccountInfo`, `getPortfolioSummary`, `getPositions`).
    -   **Verification**: The API client can be imported and used in components.

-   [x] **Task 3.2: Display Account Information**
    -   **Dependency**: Task 3.1
    -   **Action**: Create an `AccountInfo` component.
    -   **Action**: Use the `apiClient` to fetch data from the `/account/info` endpoint and display it.
    -   **Action**: Use MUI `Card` and `Typography` components to present the data clearly (e.g., Owner, Cash Balance).
    -   **Verification**: The component correctly displays account information on the dashboard.

-   [x] **Task 3.3: Display Positions Table**
    -   **Dependency**: Task 3.1
    -   **Action**: Create a `PositionsTable` component.
    -   **Action**: Use the MUI `<DataGrid>` component to display the list of positions fetched from `/portfolio/positions`.
    -   **Action**: Implement columns for Symbol, Quantity, Average Price, and Value.
    -   **Action**: Apply conditional styling for profit/loss values based on the style guide.
    -   **Verification**: The data grid populates with position data from the backend and is styled correctly.

---

## Phase 4: Basic Trading & Order Management ✅

**Status: COMPLETED**
**Goal**: Implement the core user workflow for creating and viewing orders.

-   [x] **Task 4.1: Create Order Entry Form**
    -   **Dependency**: Phase 3
    -   **Action**: Create a `CreateOrderForm` component.
    -   **Action**: Use MUI form components (`TextField`, `Select`, `Button`) to build a form for submitting stock orders (Symbol, Quantity, Type, Price).
    -   **Action**: Add client-side validation for the form fields.
    -   **Verification**: The form renders correctly and enforces validation rules.

-   [x] **Task 4.2: Implement Order Creation Logic**
    -   **Dependency**: Task 4.1
    -   **Action**: Connect the `CreateOrderForm`'s submit handler to the `create_order` function in the `apiClient`.
    -   **Action**: Display success or error feedback to the user after a submission attempt using MUI `Snackbar` or `Alert` components.
    -   **Verification**: Submitting a valid order in the form successfully creates an order in the backend.

-   [x] **Task 4.3: Display Order History**
    -   **Dependency**: Task 3.1
    -   **Action**: Create an `OrdersTable` component using MUI's `<DataGrid>`.
    -   **Action**: Fetch and display recent orders from the `/orders` endpoint.
    -   **Action**: Use MUI's `Chip` component to create status badges as defined in the style guide (`PENDING`, `FILLED`, `CANCELLED`).
    -   **Verification**: The table correctly displays a list of orders and their statuses.

-   [x] **Task 4.4: Implement Order Cancellation**
    -   **Dependency**: Task 4.3
    -   **Action**: Add a "Cancel" button to each `PENDING` order in the `OrdersTable`.
    -   **Action**: Wire the button to call the `cancel_order` API endpoint via the `apiClient`.
    -   **Action**: On successful cancellation, refresh the order list to show the updated `CANCELLED` status.
    -   **Verification**: Clicking the cancel button successfully cancels the order in the backend and updates the UI.
