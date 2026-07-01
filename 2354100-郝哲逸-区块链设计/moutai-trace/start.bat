@echo off
chcp 65001 >nul
echo ========================================
echo   Moutai Trace Blockchain System
echo ========================================
echo.

echo [1] Starting Hardhat Node...
start "Hardhat Node" cmd /k "npx hardhat node"

echo Waiting for node to start...
timeout /t 5 /nobreak > nul

echo.
echo [2] Deploying Smart Contract...
call npx hardhat run scripts/deploy.js --network localhost

echo.
echo [3] Starting Frontend Server...
cd frontend
start "Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo   System Started!
echo   Frontend: http://localhost:5173
echo ========================================
echo.
echo Please enter the contract address in settings
pause
