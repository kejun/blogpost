# 🚀 Repository Setup Guide

This guide helps you set up the two new repositories for **MCP Memory Server** and **MiniClaw**.

---

## 📦 Repository 1: MCP Memory Server

**Purpose:** Production-ready memory service for AI Agents using MCP Protocol

**Location:** `/home/openclawuser/.openclaw/workspace/mcp-memory-server`

### Step 1: Create GitHub Repository

Go to GitHub and create a new repository:
- **Name:** `mcp-memory-server`
- **Visibility:** Public (recommended for open source)
- **Initialize:** Do NOT initialize with README (we already have one)

### Step 2: Push to GitHub

```bash
cd /home/openclawuser/.openclaw/workspace/mcp-memory-server

# Rename branch to main (if needed)
git branch -m main

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/mcp-memory-server.git

# Push to GitHub
git push -u origin main
```

Or using SSH (if you have SSH keys configured):

```bash
git remote add origin git@github.com:YOUR_USERNAME/mcp-memory-server.git
git push -u origin main
```

### Step 3: Verify

Visit `https://github.com/YOUR_USERNAME/mcp-memory-server` to confirm the code is uploaded.

---

## 🦎 Repository 2: MiniClaw

**Purpose:** Minimal viable Claws prototype for learning and experimentation

**Location:** `/home/openclawuser/.openclaw/workspace/miniclaw`

### Step 1: Create GitHub Repository

Go to GitHub and create a new repository:
- **Name:** `miniclaw`
- **Visibility:** Public (recommended for educational purposes)
- **Initialize:** Do NOT initialize with README (we already have one)

### Step 2: Push to GitHub

```bash
cd /home/openclawuser/.openclaw/workspace/miniclaw

# Rename branch to main (if needed)
git branch -m main

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/miniclaw.git

# Push to GitHub
git push -u origin main
```

Or using SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/miniclaw.git
git push -u origin main
```

### Step 3: Verify

Visit `https://github.com/YOUR_USERNAME/miniclaw` to confirm the code is uploaded.

---

## 🔗 Cross-Linking

After both repositories are on GitHub, update the links in README files:

### In `mcp-memory-server/README.md`:

Find and replace:
```markdown
[GitHub]: https://github.com/kejun/mcp-memory-server
```

With your actual URL.

### In `miniclaw/README.md`:

Find and replace:
```markdown
[GitHub]: https://github.com/kejun/miniclaw
```

With your actual URL.

### In Blog Post Articles:

Update links in:
- `blogpost/2026-02-24-agentic-engineering-practical-guide.md`
- `blogpost/2026-02-24-claws-architecture-deep-dive.md`

Replace example URLs with your actual repository URLs.

---

## 📝 Next Steps

### 1. Add LICENSE Files

Both repositories should include an MIT license:

```bash
# For mcp-memory-server
cd /home/openclawuser/.openclaw/workspace/mcp-memory-server
echo "MIT License - see https://opensource.org/licenses/MIT" > LICENSE
git add LICENSE
git commit -m "Add MIT License"
git push

# For miniclaw
cd /home/openclawuser/.openclaw/workspace/miniclaw
echo "MIT License - see https://opensource.org/licenses/MIT" > LICENSE
git add LICENSE
git commit -m "Add MIT License"
git push
```

### 2. Add CONTRIBUTING Guides

Create `CONTRIBUTING.md` files with contribution guidelines.

### 3. Set Up GitHub Issues

Enable GitHub Issues in repository settings for bug reports and feature requests.

### 4. Configure GitHub Actions (Optional)

Add CI/CD workflows for:
- Automated testing
- Linting and formatting checks
- NPM package publishing (for mcp-memory-server)

### 5. Publish to NPM (For MCP Memory Server)

```bash
cd /home/openclawuser/.openclaw/workspace/mcp-memory-server
npm login
npm publish
```

---

## 🎯 Quick Reference

| Repository | Purpose | Tech Stack | Target Users |
|------------|---------|------------|--------------|
| **mcp-memory-server** | Production memory service | TypeScript, MCP, Qdrant, SQLite | Production deployments |
| **miniclaw** | Educational prototype | TypeScript, llama.cpp, SQLite | Learning & experimentation |

---

## ❓ Troubleshooting

### "remote origin already exists"

```bash
git remote remove origin
git remote add origin <your-url>
```

### "permission denied"

Make sure you're using the correct authentication:
- HTTPS: Use personal access token or GitHub CLI
- SSH: Ensure SSH keys are added to GitHub

### "src refspec main does not match any"

```bash
git branch -a  # Check available branches
git push -u origin master  # If branch is still called master
```

---

## 📞 Support

If you encounter issues:
1. Check GitHub's documentation: https://docs.github.com/
2. Review Git basics: https://git-scm.com/doc
3. Open an issue in the respective repository

---

*Guide created: 2026-02-24 | OpenClaw Team*
