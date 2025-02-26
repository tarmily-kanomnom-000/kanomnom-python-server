from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Ka-nom nom Service Monitor"
    DEBUG: bool = False
    
    # Add your configuration variables here
    
    class Config:
        case_sensitive = True

settings = Settings() 