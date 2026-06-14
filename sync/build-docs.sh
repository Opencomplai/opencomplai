#!/bin/bash
set -e

echo "🔨 Building OpenComplai Documentation..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check Python/MkDocs
echo -e "${BLUE}📋 Checking MkDocs installation...${NC}"
if ! command -v mkdocs &> /dev/null; then
    echo -e "${RED}❌ MkDocs not installed${NC}"
    echo "   Run: pip install -r requirements-docs.txt"
    exit 1
fi

# Build documentation
echo -e "${YELLOW}📚 Building documentation...${NC}"
cd docs/
mkdocs build --strict

# Return to repo root
cd ..

# Create build manifest
echo -e "${YELLOW}📝 Creating build manifest...${NC}"
cat > docs/site/build-manifest.json <<EOF
{
  "version": "$(git describe --tags 2>/dev/null || echo 'dev')",
  "commit": "$(git rev-parse --short HEAD)",
  "commit_hash": "$(git rev-parse HEAD)",
  "branch": "$(git rev-parse --abbrev-ref HEAD)",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "build_source": "opencomplai"
}
EOF

# Statistics
echo ""
echo -e "${GREEN}✅ Documentation built successfully!${NC}"
echo -e "${GREEN}📍 Output location: ./docs/site${NC}"
FILE_COUNT=$(find docs/site -type f | wc -l)
echo -e "${GREEN}📊 Total files: $FILE_COUNT${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Run: mkdocs serve (to preview locally)"
echo "  2. Visit: http://127.0.0.1:8000"
