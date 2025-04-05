from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from mistralai import Mistral
from typing import Optional
import os
import uuid

load_dotenv()  # Charge les variables depuis .env

# Initialisation du client Mistral avec la clé API
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("MISTRAL_API_KEY n'est pas défini dans les variables d'environnement.")

client = Mistral(api_key=api_key)
model = "mistral-large-latest"

# Configuration de la base de données
DATABASE_URL = "sqlite:///./roadbook.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modèle de la base de données
class Journey(Base):
    __tablename__ = "journey"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    description = Column(Text)
    ai_response = Column(Text) 

# Création des tables
Base.metadata.create_all(bind=engine)

# Schéma Pydantic pour la validation des données
class JourneyCreate(BaseModel):
    name: str
    description: str
    ai_response: Optional[str] = None

class JourneyResponse(JourneyCreate):
    id: str
    name: str
    description: str
    ai_response: Optional[str] = None 

# Dépendance pour obtenir une session de base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialisation de l'application FastAPI
app = FastAPI()

# Ajouter CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permet toutes les origines, à adapter si tu veux limiter
    allow_credentials=True,
    allow_methods=["*"],  # Permet toutes les méthodes HTTP (GET, POST, etc.)
    allow_headers=["*"],  # Permet tous les en-têtes
)

class ChatRequest(BaseModel):
    message: str

@app.post("/journey/chat")
async def chat_with_mistral(journey: JourneyCreate, db: Session = Depends(get_db)):
    try:
        chat_response = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": journey.description}]
        )

        ai_response = chat_response.choices[0].message.content

        # Enregistrement dans la base de données
        


        new_journey = Journey(
            id=str(uuid.uuid4()),  # Génération d'un UUID unique
            name=journey.name,
            description=journey.description,
            ai_response=ai_response
        )
        db.add(new_journey)
        db.commit()
        db.refresh(new_journey)
        

        return {"response": ai_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bonjour/{name}")
async def root(name: str):
    return {"greeting": f"Hello, {name}"}
    
# Routes CRUD
@app.post("/journeys/", response_model=JourneyResponse)
def create_journey(journey: JourneyCreate, db: Session = Depends(get_db)):
    db_journey = Journey(name=journey.name, description=journey.description)
    db.add(db_journey)
    db.commit()
    db.refresh(db_journey)
    return db_journey

@app.get("/journeys/{journey_id}", response_model=JourneyResponse)
def read_journey(journey_id: str, db: Session = Depends(get_db)):
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise HTTPException(status_code=404, detail="Journey not found")
    return journey

@app.get("/journeys/", response_model=list[JourneyResponse])
def read_journeys(db: Session = Depends(get_db)):
    return db.query(Journey).all()

@app.put("/journeys/{journey_id}", response_model=JourneyResponse)
def update_journey(journey_id: str, journey: JourneyCreate, db: Session = Depends(get_db)):
    db_journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if db_journey is None:
        raise HTTPException(status_code=404, detail="Journey not found")
    db_journey.name = journey.name
    db_journey.description = journey.description
    db.commit()
    db.refresh(db_journey)
    return db_journey

@app.delete("/journeys/{journey_id}")
def delete_journey(journey_id: str, db: Session = Depends(get_db)):
    db_journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if db_journey is None:
        raise HTTPException(status_code=404, detail="Journey not found")
    db.delete(db_journey)
    db.commit()
    return {"message": "Journey deleted successfully"}
    
