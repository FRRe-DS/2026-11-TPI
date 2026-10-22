require('dotenv').config();
const { Client } = require('pg');

const client = new Client({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  ssl: { rejectUnauthorized: false } // Obligatorio para conexiones externas a Supabase
});

async function probarConexion() {
  try {
    await client.connect();
    console.log('✅ Conexión exitosa a Supabase PostgreSQL');

    const res = await client.query('SELECT current_database() AS bd, NOW() AS hora_servidor;');
    console.log('📊 Datos del servidor:', res.rows[0]);
  } catch (error) {
    console.error('❌ Error al conectar a la base de datos:', error.message);
  } finally {
    await client.end();
  }
}

probarConexion();