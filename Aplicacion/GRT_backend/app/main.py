from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Controlador.excel_controlador import router

# Crea la aplicación FastAPI
app = FastAPI()

# Configura CORS para permitir peticiones desde cualquier origen (solo desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://grt-rho.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Registra las rutas del controlador de Excel
app.include_router(router)
