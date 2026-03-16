from pydantic import BaseModel
from typing import Dict, List, Optional, Any

class GameMetadata(BaseModel):
    title: str
    summary: str
    genre: str
    characters: List[str] = []
    backgrounds: List[str] = []
    scenes: List[str] = []
    variables: List[str] = []
    starting_point: str = "main"
    plot_outline: Optional[str] = None
    prompt_prefix: Optional[str] = None

class SessionState(BaseModel):
    session_id: str
    current_label: str = "main"
    line_index: int = 0
    variables: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    dialogue_log: List[Dict[str, str]] = []
    last_type: str = "talk"
    last_choice_index: Optional[int] = None

class GameUpdate(BaseModel):
    command: str

class CreateGameRequest(BaseModel):
    name: str
    prompt: Optional[str] = None
    manual_data: Optional[GameMetadata] = None

class GenerateRequest(BaseModel):
    target: str
    category: Optional[str] = "characters"
    sub_type: Optional[str] = "description"

class DialogueResponse(BaseModel):
    type: str # talk, choice, end, missing_label
    character: Optional[str] = None
    text: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    current_label: Optional[str] = None
    line_index: Optional[int] = None
    background: Optional[str] = None
    background_desc: Optional[str] = None
    active_scene: Optional[Dict[str, str]] = None 
    active_animation: Optional[Dict[str, str]] = None
    variables: Optional[Dict[str, Any]] = None
    dialogue_log: Optional[List[Dict[str, str]]] = None
