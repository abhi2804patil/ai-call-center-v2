# AI Call Center SaaS Platform

AI-powered call center platform that uses **pre-generated audio** with **Sarvam AI TTS/STT** and **Google Gemini intent classification** to automate phone calls in 11 Indian languages.

## Architecture

```
Customer Phone <-> Exotel (Telephony) <-> Call Orchestrator
                                              |
                                    +---------+---------+
                                    |         |         |
                              Sarvam STT  Gemini AI  Pre-generated
                              (Speech to  (Intent    Audio (S3)
                               Text)      Classify)
```

### How a Call Works

1. **Script Creation**: Company writes a call script with multiple nodes (greeting, interested, not_interested, etc.) in multiple languages
2. **Audio Generation**: System generates audio for every node in every language using Sarvam TTS and stores in S3
3. **Campaign Launch**: Company uploads CSV with phone numbers and starts campaign
4. **Call Execution**:
   - Exotel connects the call
   - System plays pre-generated greeting audio
   - For dynamic data (name, amount) - generates real-time TTS with same voice
   - Customer speaks -> Sarvam STT transcribes
   - Gemini classifies intent (interested/not_interested/callback/transfer)
   - System plays matching pre-generated audio response
   - Repeat until call ends or transfers to human
5. **Post-Call**: Gemini generates summary, sentiment score, and outcome tags

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI (async) |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Database | PostgreSQL 16 + Redis 7 |
| AI - Speech | Sarvam AI (STT + TTS) |
| AI - Intent | Google Gemini 2.5 Flash |
| Telephony | Exotel |
| Storage | AWS S3 |
| Task Queue | Celery + Redis |
| Real-time | WebSocket + Redis Pub/Sub |

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd ai-call-center

# 2. Copy environment files
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 3. Start all services
docker-compose up --build

# 4. Access the app
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Backend:  http://localhost:8000/health
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET_KEY` | Secret for JWT token signing |
| `SARVAM_API_KEY` | Sarvam AI API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `EXOTEL_SID` | Exotel Account SID |
| `EXOTEL_API_KEY` | Exotel API Key |
| `EXOTEL_API_TOKEN` | Exotel API Token |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 |
| `AWS_S3_BUCKET` | S3 bucket name for audio storage |

## API Endpoints

| Route | Description |
|-------|-------------|
| `POST /api/v1/auth/register` | Register company + admin user |
| `POST /api/v1/auth/login` | Login |
| `GET /api/v1/scripts` | List scripts |
| `POST /api/v1/scripts` | Create script |
| `POST /api/v1/audio/generate/{id}` | Generate audio for script |
| `POST /api/v1/campaigns` | Create campaign |
| `POST /api/v1/campaigns/{id}/upload-phones` | Upload phone list CSV |
| `POST /api/v1/campaigns/{id}/start` | Start campaign |
| `GET /api/v1/calls` | List call logs |
| `GET /api/v1/calls/live` | Live active calls |
| `GET /api/v1/analytics/dashboard` | Analytics dashboard |
| `WS /ws/calls/{company_id}` | Live call monitoring |

## Folder Structure

```
ai-call-center/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── workers/      # Celery tasks
│   │   └── utils/        # Helpers
│   ├── alembic/          # Database migrations
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── lib/          # API client, store
│   │   ��── components/   # Reusable components
│   └── Dockerfile
├── docker-compose.yml
└── SAMPLE_SCRIPT.json
```

## Supported Languages

Hindi, English, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi
