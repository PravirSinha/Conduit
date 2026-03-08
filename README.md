# Conduit

Project scaffold for multi-agent automotive operations.

## EC2 bootstrap (Ubuntu 22.04)

Use the bootstrap script to install Docker, Docker Compose plugin, AWS CLI, and prepare `.env`.

```bash
chmod +x scripts/ec2_init.sh
./scripts/ec2_init.sh --repo-url <your-git-repo-url> --branch main --app-dir ~/conduit
```

If your repo is already present at `~/conduit`, run without `--repo-url`:

```bash
./scripts/ec2_init.sh --branch main --app-dir ~/conduit
```

### First deploy

1. Edit `~/conduit/.env` and set required secrets (`OPENAI_API_KEY`, `PINECONE_API_KEY`) and production `DATABASE_URL` (RDS private endpoint).
2. Deploy:

```bash
cd ~/conduit
docker compose up -d --build
```

3. Verify:

```bash
curl http://localhost:8000/health
docker compose ps
docker compose logs -f app
```

4. After first successful migration+seed, set `RUN_SEED_ON_STARTUP=false` in `.env`.
