# Animal-AN-ERP System

An Enterprise Resource Planning (ERP) system designed for Animal-An, a regional reseller specializing in animal health products distribution. This offline system manages inventory, sales, and financial transactions for veterinary medicines, vaccines, and medicated feed products.

## Business Overview

Animal-An is a regional distributor of:
- Veterinary medicines
- Animal vaccines
- Medicated feed products
- Animal health supplements

## Technical Specifications

### Database System
- SQLite 3 with SQLAlchemy 2.0.25
- Fully offline operation
- Single-file database storage
- Automatic backup system
- No external database server required

### System Requirements

#### Hardware Requirements
- Windows 11 Operating System
- Minimum 8GB RAM
- 1920x1080 screen resolution recommended
- 10GB free disk space for database and backups

#### Software Requirements
- Python 3.9+
- SQLAlchemy 2.0.25
- PyQt5 for user interface
- No internet connection required for operation

## Installation

1. System Preparation:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate     # For Windows

# Install core requirements
pip install sqlalchemy==2.0.25
pip install pyqt5==5.15.9
```

2. Install Additional Requirements:
```bash
pip install -r requirements.txt
```

3. Initialize Database:
```bash
python -m models.database
```

4. Run Application:
```bash
python main.py
```

## Database Management

### Automatic Backups
The system automatically creates database backups:
- Daily backups during first launch
- Backup before major operations
- Custom backup scheduling available

### Backup Location
```
animal-an-erp/
├── data/
│   ├── animal_an.db        # Main database
│   └── backups/            # Backup storage
```

### Manual Backup
```bash
python utils/backup.py create
```

### Restore from Backup
```bash
python utils/backup.py restore YYYYMMDD_HHMMSS
```

## Features

### Inventory Management
- Product tracking with batch numbers
- Expiration date monitoring
- Storage condition tracking (temperature)
- Stock level alerts
- Multiple package types support

### Sales and Distribution
- Customer order processing
- Delivery tracking
- Special handling requirements
- Invoice generation

### Financial Management
- Supplier payment tracking
- Customer billing
- Credit term monitoring
- Payment status tracking

## Project Structure

```
animal-an-erp/
├── config/         # Configuration files
│   └── database.py # Database configuration
├── data/          # Database storage
│   ├── animal_an.db
│   └── backups/
├── models/        # SQLAlchemy models
├── viewmodels/    # Business logic
├── views/         # PyQt5 UI components
├── utils/         # Utilities
│   ├── backup.py
│   └── database.py
├── static/        # Resources
└── logs/          # System logs
```

## Data Security

### Local Storage
- All data stored locally in SQLite database
- No external connections required
- Encrypted database file (optional)

### Backup System
- Automated daily backups
- Multiple backup retention
- Point-in-time recovery capability

### Access Control
- User authentication
- Role-based permissions
- Activity logging

## Maintenance

### Database Optimization
```bash
# Optimize database
python utils/database.py optimize

# Verify database integrity
python utils/database.py verify
```

### Backup Management
```bash
# List all backups
python utils/backup.py list

# Clean old backups
python utils/backup.py clean --days 30
```

## Troubleshooting

### Database Issues
1. Check database integrity:
```bash
python utils/database.py check
```

2. Repair database (if needed):
```bash
python utils/database.py repair
```

3. Compact database:
```bash
python utils/database.py vacuum
```

### Common Issues
- Database locked: Close all other applications accessing the database
- Backup failed: Ensure sufficient disk space
- Slow performance: Run database optimization

## Support and Updates

### Local Support
- System administrator manual included
- Local database maintenance guide
- Backup and recovery procedures

### Version Information
- Current Version: 1.0.0
- SQLAlchemy Version: 2.0.25
- SQLite Version: 3.x
- Python Version: 3.9+

## Development Notes

### Database Development
- Use SQLAlchemy models for data structure
- Follow type hints for better reliability
- Implement proper transaction management
- Regular database maintenance required

### Best Practices
1. Regular backups
2. Database optimization
3. Log monitoring
4. Data validation

## License

[MIT License](LICENSE)