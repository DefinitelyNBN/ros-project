#!/bin/bash
# =============================================================================
#  ROS Attendance Bot — Raspberry Pi 4B Automated Setup & Optimization Script
# =============================================================================
#  Run this script on your Raspberry Pi 4B:
#      chmod +x pi_setup.sh
#      ./pi_setup.sh
# =============================================================================

set -e

echo "══════════════════════════════════════════════════════════════════"
echo "  🤖  ROS Attendance Bot — Raspberry Pi 4B Setup & Optimizer"
echo "══════════════════════════════════════════════════════════════════"

# 1. Check Architecture
ARCH=$(uname -m)
echo "🔍 Detected architecture: $ARCH"

# 2. Increase Swap Space (Essential for dlib compilation on Pi 4B)
echo ""
echo "⚙️ [1/5] Checking swap memory..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
echo "   Total RAM: ${TOTAL_RAM_MB} MB"

if [ -f /etc/dphys-swapfile ]; then
    CURRENT_SWAP=$(grep "^CONF_SWAPSIZE" /etc/dphys-swapfile | cut -d'=' -f2)
    echo "   Current swap: ${CURRENT_SWAP} MB"
    if [ "$CURRENT_SWAP" -lt 2048 ]; then
        echo "   Increasing swap to 2048MB for dlib compilation..."
        sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
        sudo /etc/init.d/dphys-swapfile restart || true
        echo "   ✅ Swap memory increased to 2048 MB."
    fi
fi

# 3. Install Required System Libraries
echo ""
echo "📦 [2/5] Installing OS dependencies and BLAS accelerators..."
sudo apt-get update
sudo apt-get install -y \
    cmake \
    build-essential \
    pkg-config \
    libopenblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    v4l-utils \
    python3-dev \
    python3-pip \
    python3-tk \
    python3-numpy

# 4. Install Python Dependencies
echo ""
echo "🐍 [3/5] Installing Python packages..."
# Use pip with piwheels (enabled by default on Raspberry Pi OS)
pip3 install --upgrade pip setuptools wheel
pip3 install -r requirements.txt

# 5. Verify Camera Access
echo ""
echo "📷 [4/5] Checking camera devices..."
if [ -e /dev/video0 ]; then
    echo "   ✅ /dev/video0 detected!"
    v4l2-ctl --list-devices 2>/dev/null || true
else
    echo "   ⚠️  No /dev/video0 found. Ensure your USB camera is plugged in."
fi

# 6. Run Self-Test
echo ""
echo "🧪 [5/5] Running verification test..."
python3 -c "
import cv2, numpy, PIL, openpyxl, face_recognition
print('   ✅ OpenCV version:', cv2.__version__)
print('   ✅ face_recognition version:', face_recognition.__version__)
print('   ✅ openpyxl loaded successfully')
print('   ✅ All Pi 4B dependencies verified!')
"

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  🎉 Installation & Pi 4B Optimization Complete!"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "  ▶ To launch GUI on monitor or VNC:"
echo "      python3 main.py"
echo ""
echo "  ▶ To run headless autonomously on your robot:"
echo "      python3 headless.py --cam 0 --export-interval 10"
echo ""
echo "  ▶ To launch as a ROS node:"
echo "      python3 -c 'from recognition_engine import RecognitionEngine; print(\"Ready for ROS\")'"
echo "══════════════════════════════════════════════════════════════════"
