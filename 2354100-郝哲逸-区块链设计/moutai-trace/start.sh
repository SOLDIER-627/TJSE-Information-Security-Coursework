#!/bin/bash

echo "========================================"
echo "  Moutai Trace Blockchain System"
echo "========================================"
echo ""

# Check if in project root directory
if [ ! -f "hardhat.config.js" ]; then
    echo "Error: Please run this script in moutai-trace directory"
    exit 1
fi

echo "[1] Starting Hardhat Node..."
gnome-terminal --title="Hardhat Node" -- bash -c "npx hardhat node; exec bash" 2>/dev/null || \
xterm -title "Hardhat Node" -e "npx hardhat node; bash" 2>/dev/null || \
terminator --title "Hardhat Node" -e "npx hardhat node; bash" 2>/dev/null || \
konsole --title "Hardhat Node" -e bash -c "npx hardhat node; bash" 2>/dev/null || \
{
    echo "Cannot open new terminal, running node in background..."
    npx hardhat node &
    NODE_PID=$!
    echo "Node PID: $NODE_PID"
}

echo "Waiting for node to start..."
sleep 5

echo ""
echo "[2] Deploying Smart Contract..."
npx hardhat run scripts/deploy.js --network localhost

echo ""
echo "[3] Starting Frontend Server..."
cd frontend

gnome-terminal --title="Frontend" -- bash -c "npm run dev; exec bash" 2>/dev/null || \
xterm -title "Frontend" -e "npm run dev; bash" 2>/dev/null || \
terminator --title="Frontend" -e "npm run dev; bash" 2>/dev/null || \
konsole --title "Frontend" -e bash -c "npm run dev; bash" 2>/dev/null || \
{
    echo "Cannot open new terminal, running frontend in background..."
    npm run dev &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
}

cd ..

echo ""
echo "========================================"
echo "  System Started!"
echo "  Frontend: http://localhost:5173"
echo "========================================"
echo ""
echo "Please enter the contract address in settings"
read -p "Press Enter to continue..."
