import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import(
    ALLOWED_ORIGINS, 
    APP_DESCRIPTION, 
    APP_TITLE, 
    APP_VERSION, 
    SPACY_MODEL_PRIMARY, 
    SPACY_MODEL_SECONDARY, SENTENCE_TRANSFORMER_MODEL
)
from backend.api.routes import router

logger=logging.getLogger('ats_resume_scorer')

@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.info('Starting ATS Resume Analyzer API...')

    logger.info(f'Loading spaCy NLP model: {SPACY_MODEL_PRIMARY}')
    import spacy
    nlp = None
    try:
        nlp = spacy.load(SPACY_MODEL_PRIMARY)
        logger.info(f'Loaded {SPACY_MODEL_PRIMARY}')
    except OSError:
        logger.warning(f'{SPACY_MODEL_PRIMARY} not found locally. Attempting automatic download...')
        try:
            spacy.cli.download(SPACY_MODEL_PRIMARY)
            nlp = spacy.load(SPACY_MODEL_PRIMARY)
            logger.info(f'Downloaded and loaded {SPACY_MODEL_PRIMARY}')
        except Exception as exc:
            logger.warning(f'Could not load or download {SPACY_MODEL_PRIMARY}: {exc}. Trying fallback: {SPACY_MODEL_SECONDARY}')
            try:
                nlp = spacy.load(SPACY_MODEL_SECONDARY)
                logger.info(f'Loaded {SPACY_MODEL_SECONDARY} (fallback)')
            except OSError:
                try:
                    spacy.cli.download(SPACY_MODEL_SECONDARY)
                    nlp = spacy.load(SPACY_MODEL_SECONDARY)
                    logger.info(f'Downloaded and loaded {SPACY_MODEL_SECONDARY} (fallback)')
                except Exception as exc2:
                    logger.error(f'Failed to load secondary model {SPACY_MODEL_SECONDARY}: {exc2}. Initializing basic English pipeline...')
                    nlp = spacy.blank('en')

    app.state.nlp = nlp

    logger.info(f'Loading SentenceTransformer: {SENTENCE_TRANSFORMER_MODEL}')
    from sentence_transformers import SentenceTransformer
    try:
        app.state.embedder = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)
        logger.info(f'Loaded {SENTENCE_TRANSFORMER_MODEL}')
    except Exception as exc:
        logger.error(f'Error loading SentenceTransformer ({SENTENCE_TRANSFORMER_MODEL}): {exc}')
        raise exc

    logger.info('All models loaded. API is ready to serve requests.')

    yield

    logger.info('Shutting down the API.')


app=FastAPI(
    title=APP_TITLE, 
    description=APP_DESCRIPTION, 
    version=APP_VERSION, 
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc'
)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True, 
    allow_methods     = ['*'],
    allow_headers     = ['*'],

)

app.include_router(router)

@app.get('/')
async def root():
    return {
        'name':      'ATS Resume Analyzer API',
        'version':   '2.0.0',
        'endpoints': {
            'POST   /api/v1/analyze-resume': 'Analyze a resume',
            'GET    /api/v1/history':        'Get user history',
            'DELETE /api/v1/history/:id':    'Delete a history entry',
            'GET    /api/v1/health':         'Health check',
            'POST   /api/v1/generate-pdf':   'Generate PDF report from data',
        },
    }

if __name__=='__main__':
    import uvicorn
    uvicorn.run(
        'backend.main:app',
        host    = '0.0.0.0',
        port    = 8000,
        reload  = True,    # Auto-restart on code changes (dev only)
    )
