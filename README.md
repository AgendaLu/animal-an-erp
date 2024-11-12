# Animal-AN-ERP System

An Enterprise Resource Planning (ERP) system designed for animal-related business management.

## Setup Development Environment

1. Install Anaconda:
   - Download from: https://www.anaconda.com/download
   - Install for macOS

2. Create Conda Environment:
```bash
conda create -n animal_erp python=3.9
conda activate animal_erp
conda install sqlalchemy
conda install spyder
conda install pyqt
```

3. Install Requirements:
```bash
pip install -r requirements.txt
```

4. Run Application:
```bash
python main.py
```

## Project Structure
- `models/`: Database models and business logic
- `viewmodels/`: View models for business logic
- `views/`: User interface components
- `data/`: Database and data files
- `logs/`: Application logs

## Features
- Inventory Management
- Order Processing
- Customer Management
- Reporting System

## Development Status
🚧 Under Development
