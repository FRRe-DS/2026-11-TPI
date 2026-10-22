import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from 'typeorm';

@Entity('metodo_pago')
export class MetodoPago {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ name: 'id_cliente', type: 'varchar', length: 255 })
  idCliente: string;

  @Column({ type: 'varchar', length: 50 })
  tipo: string;

  @Column({ name: 'ultimos_cuatro_digitos', type: 'varchar', length: 4, nullable: true })
  ultimosCuatroDigitos: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  proveedor: string;

  @Column({ type: 'varchar', length: 50, default: 'ACTIVO' })
  estado: string;

  @CreateDateColumn({ name: 'fecha_creacion' })
  fechaCreacion: Date;
}