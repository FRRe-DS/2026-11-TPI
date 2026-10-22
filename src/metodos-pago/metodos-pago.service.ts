import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { MetodoPago } from './entities/metodo-pago.entity';
import { CreateMetodoPagoDto } from './dto/create-metodo-pago.dto';

@Injectable()
export class MetodosPagoService {
  constructor(
    @InjectRepository(MetodoPago)
    private metodoPagoRepository: Repository<MetodoPago>,
  ) {}

  async registrar(createDto: CreateMetodoPagoDto): Promise<MetodoPago> {
    const nuevoMetodo = this.metodoPagoRepository.create({
      idCliente: createDto.id_cliente,
      tipo: createDto.tipo,
      ultimosCuatroDigitos: createDto.ultimos_cuatro_digitos,
      proveedor: createDto.proveedor,
    });
    return this.metodoPagoRepository.save(nuevoMetodo);
  }

  async obtenerPorCliente(idCliente: string): Promise<MetodoPago[]> {
    return this.metodoPagoRepository.find({ 
      where: { idCliente, estado: 'ACTIVO' } 
    });
  }
}