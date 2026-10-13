"""REST API Perpustakaan using Flask and SQLAlchemy."""

from datetime import datetime
import os
from flask import Flask, jsonify, Response, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)

# Konfigurasi Database dengan Fallback Otomatis
MYSQL_URI = os.getenv(
    "DATABASE_URL", "mysql+pymysql://root:@localhost/db_perpustakaan"
)
SQLITE_URI = "sqlite:///db_perpustakaan.db"


def setup_database_uri() -> str:
    """Tentukan koneksi database. Jika MySQL tersedia, gunakan MySQL.

    Jika database MySQL belum ada, coba buat secara otomatis. Jika server
    MySQL tidak aktif, gunakan SQLite agar aplikasi tetap dapat berjalan.
    """
    try:
        from sqlalchemy import create_engine

        # Coba koneksi ke server MySQL (tanpa nama database)
        mysql_host = "mysql+pymysql://root:@localhost"
        temp_engine = create_engine(mysql_host, connect_args={"connect_timeout": 2})
        with temp_engine.connect() as conn:
            conn.execute(
                text("CREATE DATABASE IF NOT EXISTS db_perpustakaan")
            )
            conn.commit()
        temp_engine.dispose()
        return MYSQL_URI
    except Exception:
        # Jika MySQL tidak aktif/tidak ada, gunakan SQLite lokal
        return SQLITE_URI


app.config["SQLALCHEMY_DATABASE_URI"] = setup_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Penulis(db.Model):
    """Model untuk entity Penulis."""

    __tablename__ = "penulis"

    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    buku = db.relationship("Buku", backref="penulis", lazy=True)

    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            "id": self.id,
            "nama": self.nama,
            "email": self.email,
            "created_at": (
                self.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.created_at
                else None
            ),
        }


class Kategori(db.Model):
    """Model untuk entity Kategori."""

    __tablename__ = "kategori"

    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False)
    deskripsi = db.Column(db.Text, nullable=True)
    buku = db.relationship("Buku", backref="kategori", lazy=True)

    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            "id": self.id,
            "nama": self.nama,
            "deskripsi": self.deskripsi,
        }


class Buku(db.Model):
    """Model untuk entity Buku."""

    __tablename__ = "buku"

    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(50), unique=True, nullable=False)
    tahun_terbit = db.Column(db.Integer, nullable=False)
    harga = db.Column(db.Float, nullable=False)
    penulis_id = db.Column(
        db.Integer, db.ForeignKey("penulis.id"), nullable=False
    )
    kategori_id = db.Column(
        db.Integer, db.ForeignKey("kategori.id"), nullable=False
    )

    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            "id": self.id,
            "judul": self.judul,
            "isbn": self.isbn,
            "tahun_terbit": self.tahun_terbit,
            "harga": self.harga,
            "penulis_id": self.penulis_id,
            "kategori_id": self.kategori_id,
        }


def format_response(
    status: str, message: str, data_or_errors, code: int
) -> tuple[Response, int]:
    """Format uniform JSON response."""
    key = "data" if status == "success" else "errors"
    response = {
        "status": status,
        "message": message,
        key: data_or_errors,
    }
    return jsonify(response), code


# ==============================================================================
# Error Handlers Global (Menjamin respon selalu berupa JSON seragam)
# ==============================================================================
@app.errorhandler(400)
def handle_bad_request(error):
    """Handle 400 Bad Request with uniform JSON."""
    return format_response(
        "error", "Bad request atau data JSON tidak valid", str(error), 400
    )


@app.errorhandler(404)
def handle_not_found(error):
    """Handle 404 Not Found with uniform JSON."""
    return format_response(
        "error", "Data atau rute tidak ditemukan", {"route": "not_found"}, 404
    )


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Handle 405 Method Not Allowed with uniform JSON."""
    return format_response(
        "error", "Metode HTTP tidak diizinkan", {"method": "not_allowed"}, 405
    )


@app.errorhandler(500)
def handle_internal_server_error(error):
    """Handle 500 Internal Server Error with uniform JSON."""
    db.session.rollback()
    return format_response(
        "error", "Terjadi kesalahan pada server", {"server": "internal_error"}, 500
    )


# ==============================================================================
# Endpoints Penulis
# ==============================================================================
@app.route("/api/penulis", methods=["GET"])
def get_penulis_all() -> tuple[Response, int]:
    """Get all penulis records."""
    penulis_list = db.session.execute(db.select(Penulis)).scalars().all()
    return format_response(
        "success",
        "Data penulis berhasil diambil",
        [p.to_dict() for p in penulis_list],
        200,
    )


@app.route("/api/penulis/<int:id>", methods=["GET"])
def get_penulis_detail(id: int) -> tuple[Response, int]:
    """Get a single penulis record by ID."""
    penulis = db.get_or_404(Penulis, id)
    return format_response(
        "success",
        "Detail penulis berhasil diambil",
        penulis.to_dict(),
        200,
    )


@app.route("/api/penulis", methods=["POST"])
def create_penulis() -> tuple[Response, int]:
    """Create a new penulis record."""
    data = request.get_json(silent=True)
    if not data or not data.get("nama") or not data.get("email"):
        return format_response(
            "error",
            "Field 'nama' dan 'email' wajib diisi",
            {"field": "required"},
            400,
        )

    nama = str(data["nama"]).strip()
    email = str(data["email"]).strip()
    if not nama or not email:
        return format_response(
            "error",
            "Field 'nama' dan 'email' tidak boleh kosong",
            {"field": "empty"},
            400,
        )

    try:
        penulis = Penulis(nama=nama, email=email)
        db.session.add(penulis)
        db.session.commit()
        return format_response(
            "success",
            "Penulis berhasil ditambahkan",
            penulis.to_dict(),
            201,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "Email sudah terdaftar",
            {"email": "duplicate"},
            409,
        )


@app.route("/api/penulis/<int:id>", methods=["PUT"])
def update_penulis(id: int) -> tuple[Response, int]:
    """Update an existing penulis record."""
    penulis = db.get_or_404(Penulis, id)
    data = request.get_json(silent=True)
    if not data:
        return format_response(
            "error", "Body request tidak boleh kosong", {}, 400
        )

    if "nama" in data:
        nama = str(data["nama"]).strip()
        if not nama:
            return format_response(
                "error", "Field 'nama' tidak boleh kosong", {"nama": "empty"}, 400
            )
        penulis.nama = nama

    if "email" in data:
        email = str(data["email"]).strip()
        if not email:
            return format_response(
                "error", "Field 'email' tidak boleh kosong", {"email": "empty"}, 400
            )
        penulis.email = email

    try:
        db.session.commit()
        return format_response(
            "success",
            "Data penulis berhasil diubah",
            penulis.to_dict(),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "Email sudah digunakan oleh penulis lain",
            {"email": "duplicate"},
            409,
        )


@app.route("/api/penulis/<int:id>", methods=["DELETE"])
def delete_penulis(id: int) -> tuple[Response, int]:
    """Delete a penulis record if no related books exist."""
    penulis = db.get_or_404(Penulis, id)
    if penulis.buku:
        return format_response(
            "error",
            "Penulis masih memiliki buku dan tidak dapat dihapus",
            {"penulis": "has_books"},
            409,
        )

    db.session.delete(penulis)
    db.session.commit()
    return format_response("success", "Penulis berhasil dihapus", None, 200)


# ==============================================================================
# Endpoints Kategori
# ==============================================================================
@app.route("/api/kategori", methods=["GET"])
def get_kategori_all() -> tuple[Response, int]:
    """Get all kategori records."""
    kategori_list = db.session.execute(db.select(Kategori)).scalars().all()
    return format_response(
        "success",
        "Data kategori berhasil diambil",
        [k.to_dict() for k in kategori_list],
        200,
    )


@app.route("/api/kategori/<int:id>", methods=["GET"])
def get_kategori_detail(id: int) -> tuple[Response, int]:
    """Get a single kategori record by ID."""
    kategori = db.get_or_404(Kategori, id)
    return format_response(
        "success",
        "Detail kategori berhasil diambil",
        kategori.to_dict(),
        200,
    )


@app.route("/api/kategori", methods=["POST"])
def create_kategori() -> tuple[Response, int]:
    """Create a new kategori record."""
    data = request.get_json(silent=True)
    if not data or not data.get("nama"):
        return format_response(
            "error",
            "Field 'nama' wajib diisi",
            {"field": "required"},
            400,
        )

    nama = str(data["nama"]).strip()
    if not nama:
        return format_response(
            "error",
            "Field 'nama' tidak boleh kosong",
            {"nama": "empty"},
            400,
        )

    deskripsi = str(data.get("deskripsi", "")).strip()

    try:
        kategori = Kategori(nama=nama, deskripsi=deskripsi)
        db.session.add(kategori)
        db.session.commit()
        return format_response(
            "success",
            "Kategori berhasil ditambahkan",
            kategori.to_dict(),
            201,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "Nama kategori sudah ada",
            {"nama": "duplicate"},
            409,
        )


@app.route("/api/kategori/<int:id>", methods=["PUT"])
def update_kategori(id: int) -> tuple[Response, int]:
    """Update an existing kategori record."""
    kategori = db.get_or_404(Kategori, id)
    data = request.get_json(silent=True)
    if not data:
        return format_response(
            "error", "Body request tidak boleh kosong", {}, 400
        )

    if "nama" in data:
        nama = str(data["nama"]).strip()
        if not nama:
            return format_response(
                "error", "Field 'nama' tidak boleh kosong", {"nama": "empty"}, 400
            )
        kategori.nama = nama

    if "deskripsi" in data:
        kategori.deskripsi = str(data.get("deskripsi", "")).strip()

    try:
        db.session.commit()
        return format_response(
            "success",
            "Data kategori berhasil diubah",
            kategori.to_dict(),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "Nama kategori sudah digunakan",
            {"nama": "duplicate"},
            409,
        )


@app.route("/api/kategori/<int:id>", methods=["DELETE"])
def delete_kategori(id: int) -> tuple[Response, int]:
    """Delete a kategori record if no related books exist."""
    kategori = db.get_or_404(Kategori, id)
    if kategori.buku:
        return format_response(
            "error",
            "Kategori masih memiliki buku dan tidak dapat dihapus",
            {"kategori": "has_books"},
            409,
        )

    db.session.delete(kategori)
    db.session.commit()
    return format_response("success", "Kategori berhasil dihapus", None, 200)


# ==============================================================================
# Endpoints Buku
# ==============================================================================
@app.route("/api/buku", methods=["GET"])
def get_buku_all() -> tuple[Response, int]:
    """Get all buku records with optional filters."""
    penulis_id = request.args.get("penulis_id")
    kategori_id = request.args.get("kategori_id")
    q = request.args.get("q")

    stmt = db.select(Buku)
    if penulis_id:
        try:
            stmt = stmt.where(Buku.penulis_id == int(penulis_id))
        except ValueError:
            return format_response(
                "error",
                "Parameter penulis_id harus berupa angka",
                {"penulis_id": "invalid"},
                400,
            )

    if kategori_id:
        try:
            stmt = stmt.where(Buku.kategori_id == int(kategori_id))
        except ValueError:
            return format_response(
                "error",
                "Parameter kategori_id harus berupa angka",
                {"kategori_id": "invalid"},
                400,
            )

    if q:
        stmt = stmt.where(Buku.judul.ilike(f"%{q.strip()}%"))

    buku_list = db.session.execute(stmt).scalars().all()
    return format_response(
        "success",
        "Data buku berhasil diambil",
        [b.to_dict() for b in buku_list],
        200,
    )


@app.route("/api/buku/<int:id>", methods=["GET"])
def get_buku_detail(id: int) -> tuple[Response, int]:
    """Get a single buku record by ID."""
    buku = db.get_or_404(Buku, id)
    return format_response(
        "success",
        "Detail buku berhasil diambil",
        buku.to_dict(),
        200,
    )


@app.route("/api/buku", methods=["POST"])
def create_buku() -> tuple[Response, int]:
    """Create a new buku record."""
    data = request.get_json(silent=True)
    required_fields = [
        "judul",
        "isbn",
        "tahun_terbit",
        "harga",
        "penulis_id",
        "kategori_id",
    ]
    if not data or not all(field in data for field in required_fields):
        return format_response(
            "error",
            "Semua field buku wajib diisi",
            {"fields": "required"},
            400,
        )

    # Validasi tipe data dan nilai
    judul = str(data["judul"]).strip()
    isbn = str(data["isbn"]).strip()
    if not judul or not isbn:
        return format_response(
            "error",
            "Field judul dan isbn tidak boleh kosong",
            {"fields": "empty"},
            400,
        )

    try:
        tahun_terbit = int(data["tahun_terbit"])
        harga = float(data["harga"])
        penulis_id = int(data["penulis_id"])
        kategori_id = int(data["kategori_id"])
    except (ValueError, TypeError):
        return format_response(
            "error",
            "Format angka pada tahun_terbit, harga, penulis_id, atau kategori_id tidak valid",
            {"type": "invalid"},
            400,
        )

    if harga < 0:
        return format_response(
            "error",
            "Harga buku tidak boleh negatif",
            {"harga": "negative"},
            400,
        )

    if not db.get(Penulis, penulis_id):
        return format_response(
            "error",
            "Penulis ID tidak ditemukan",
            {"penulis_id": "not_found"},
            404,
        )
    if not db.get(Kategori, kategori_id):
        return format_response(
            "error",
            "Kategori ID tidak ditemukan",
            {"kategori_id": "not_found"},
            404,
        )

    try:
        buku = Buku(
            judul=judul,
            isbn=isbn,
            tahun_terbit=tahun_terbit,
            harga=harga,
            penulis_id=penulis_id,
            kategori_id=kategori_id,
        )
        db.session.add(buku)
        db.session.commit()
        return format_response(
            "success",
            "Buku berhasil ditambahkan",
            buku.to_dict(),
            201,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "ISBN sudah terdaftar",
            {"isbn": "duplicate"},
            409,
        )


@app.route("/api/buku/<int:id>", methods=["PUT"])
def update_buku(id: int) -> tuple[Response, int]:
    """Update an existing buku record."""
    buku = db.get_or_404(Buku, id)
    data = request.get_json(silent=True)
    if not data:
        return format_response(
            "error", "Body request tidak boleh kosong", {}, 400
        )

    if "judul" in data:
        judul = str(data["judul"]).strip()
        if not judul:
            return format_response(
                "error", "Field judul tidak boleh kosong", {"judul": "empty"}, 400
            )
        buku.judul = judul

    if "isbn" in data:
        isbn = str(data["isbn"]).strip()
        if not isbn:
            return format_response(
                "error", "Field isbn tidak boleh kosong", {"isbn": "empty"}, 400
            )
        buku.isbn = isbn

    if "tahun_terbit" in data:
        try:
            buku.tahun_terbit = int(data["tahun_terbit"])
        except (ValueError, TypeError):
            return format_response(
                "error", "tahun_terbit harus berupa angka integer", {"tahun_terbit": "invalid"}, 400
            )

    if "harga" in data:
        try:
            harga = float(data["harga"])
            if harga < 0:
                return format_response(
                    "error", "Harga tidak boleh negatif", {"harga": "negative"}, 400
                )
            buku.harga = harga
        except (ValueError, TypeError):
            return format_response(
                "error", "harga harus berupa angka", {"harga": "invalid"}, 400
            )

    if "penulis_id" in data:
        try:
            penulis_id = int(data["penulis_id"])
        except (ValueError, TypeError):
            return format_response(
                "error", "penulis_id harus berupa angka integer", {"penulis_id": "invalid"}, 400
            )
        if not db.get(Penulis, penulis_id):
            return format_response(
                "error", "Penulis ID tidak ditemukan", {"penulis_id": "not_found"}, 404
            )
        buku.penulis_id = penulis_id

    if "kategori_id" in data:
        try:
            kategori_id = int(data["kategori_id"])
        except (ValueError, TypeError):
            return format_response(
                "error", "kategori_id harus berupa angka integer", {"kategori_id": "invalid"}, 400
            )
        if not db.get(Kategori, kategori_id):
            return format_response(
                "error", "Kategori ID tidak ditemukan", {"kategori_id": "not_found"}, 404
            )
        buku.kategori_id = kategori_id

    try:
        db.session.commit()
        return format_response(
            "success",
            "Data buku berhasil diubah",
            buku.to_dict(),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        return format_response(
            "error",
            "ISBN sudah digunakan oleh buku lain",
            {"isbn": "duplicate"},
            409,
        )


@app.route("/api/buku/<int:id>", methods=["DELETE"])
def delete_buku(id: int) -> tuple[Response, int]:
    """Delete a buku record by ID."""
    buku = db.get_or_404(Buku, id)
    db.session.delete(buku)
    db.session.commit()
    return format_response("success", "Buku berhasil dihapus", None, 200)


# ==============================================================================
# Inisialisasi Database & Menjalankan Server
# ==============================================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print(f"[OK] Database siap digunakan menggunakan: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.run(debug=True)