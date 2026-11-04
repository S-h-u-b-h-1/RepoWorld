"""Fully fictional, offline-ready repository for first-run exploration."""

from __future__ import annotations

DEMO_MODULES = [
    ("apps/web", "Web app", "frontend", 28, "Customer-facing storefront, routing and page composition.", ["apps/web/src/app.tsx", "apps/web/src/routes.tsx", "apps/web/src/layout.tsx"]),
    ("apps/web/components", "UI components", "frontend", 46, "Reusable catalog, basket and account components.", ["apps/web/components/ProductCard.tsx", "apps/web/components/CartDrawer.tsx"]),
    ("apps/web/hooks", "Client hooks", "frontend", 13, "Client-side state and API query hooks.", ["apps/web/hooks/useCart.ts", "apps/web/hooks/useProducts.ts"]),
    ("apps/admin", "Admin console", "frontend", 19, "Operator views for managing products and orders.", ["apps/admin/src/dashboard.tsx", "apps/admin/src/orders.tsx"]),
    ("services/gateway", "API gateway", "api", 21, "Public HTTP route handlers and request contracts.", ["services/gateway/src/routes.ts", "services/gateway/src/middleware.ts"]),
    ("services/auth", "Authentication", "security", 12, "Session verification and account identity services.", ["services/auth/src/sessions.ts", "services/auth/src/tokens.ts"]),
    ("services/catalog", "Catalog service", "service", 24, "Product lookup, pricing and availability logic.", ["services/catalog/src/search.py", "services/catalog/src/products.py"]),
    ("services/orders", "Order service", "service", 33, "Order lifecycle and cart checkout orchestration.", ["services/orders/src/checkout.py", "services/orders/src/fulfillment.py"]),
    ("services/payments", "Payments", "service", 15, "Payment-intent creation and payment-state handling.", ["services/payments/src/intent.py", "services/payments/src/webhooks.py"]),
    ("packages/ui", "Design system", "library", 37, "Shared tokens, UI primitives and accessibility helpers.", ["packages/ui/src/button.tsx", "packages/ui/src/tokens.ts"]),
    ("packages/types", "Shared contracts", "library", 18, "Shared schema definitions and domain types.", ["packages/types/src/product.ts", "packages/types/src/order.ts"]),
    ("packages/sdk", "API client SDK", "library", 12, "Typed API client functions for frontend consumers.", ["packages/sdk/src/client.ts", "packages/sdk/src/catalog.ts"]),
    ("data/postgres", "PostgreSQL", "database", 11, "Database schema definitions and migrations.", ["data/postgres/schema.sql", "data/postgres/migrations/001_init.sql"]),
    ("data/redis", "Redis cache", "database", 8, "Cache adapters and short-lived session state.", ["data/redis/client.py", "data/redis/cache.py"]),
    ("infra/docker", "Containers", "infra", 7, "Development and deployment container configurations.", ["infra/docker/compose.yml", "infra/docker/Dockerfile"]),
    ("infra/terraform", "Infrastructure", "infra", 12, "Declarative cloud infrastructure manifests.", ["infra/terraform/main.tf", "infra/terraform/network.tf"]),
    ("tests/e2e", "E2E tests", "test", 17, "Cross-service end-to-end scenarios.", ["tests/e2e/checkout.spec.ts", "tests/e2e/auth.spec.ts"]),
    ("docs/architecture", "Architecture docs", "docs", 9, "Design decisions and system diagrams.", ["docs/architecture/overview.md", "docs/architecture/adr-001.md"]),
]

# These are authored facts for a fictional repo, not claims about a public GitHub project.
DEMO_IMPORTS = [
    ("apps/web", "apps/web/components"),
    ("apps/web", "apps/web/hooks"),
    ("apps/web", "packages/sdk"),
    ("apps/web/components", "packages/ui"),
    ("apps/web/hooks", "packages/sdk"),
    ("apps/admin", "packages/ui"),
    ("apps/admin", "packages/sdk"),
    ("packages/sdk", "packages/types"),
    ("packages/sdk", "services/gateway"),
    ("services/gateway", "services/auth"),
    ("services/gateway", "services/catalog"),
    ("services/gateway", "services/orders"),
    ("services/catalog", "data/postgres"),
    ("services/catalog", "data/redis"),
    ("services/catalog", "packages/types"),
    ("services/orders", "services/payments"),
    ("services/orders", "data/postgres"),
    ("services/orders", "packages/types"),
    ("services/payments", "data/postgres"),
    ("services/auth", "data/redis"),
    ("tests/e2e", "apps/web"),
    ("tests/e2e", "services/gateway"),
]


def build_demo() -> dict:
    nodes = [
        {
            "id": path,
            "name": name,
            "path": path,
            "kind": kind,
            "fileCount": files,
            "description": description,
            "files": sources,
            "sampled": True,
        }
        for path, name, kind, files, description, sources in DEMO_MODULES
    ]
    edges = [
        {"source": src, "target": dest, "type": "import", "count": 1, "evidence": ["Fictional sample link"]}
        for src, dest in DEMO_IMPORTS
    ]
    return {
        "name": "Orbit Commerce",
        "owner": "Repoworld Studio",
        "description": "A fictional full-stack commerce monorepo, designed to demonstrate RepoWorld's spatial architecture explorer.",
        "url": "",
        "branch": "main",
        "source": "demo",
        "stars": 0,
        "language": "TypeScript · Python",
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "modules": len(nodes),
            "files": sum(n[3] for n in DEMO_MODULES),
            "dependencies": len(edges),
            "inspectedSources": 0,
            "partial": False,
        },
        "warnings": ["Fictional demonstration data. Open a public GitHub repository to analyze actual code."],
    }
