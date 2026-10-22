import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Pago } from './entities/pago.entity';
import { ProcesarPagoDto } from './dto/procesar-pago.dto';

@Injectable()
export class PagosService {
  constructor(
    @InjectRepository(Pago)
    private pagoRepository: Repository<Pago>,
  ) {}

  async procesar(dto: ProcesarPagoDto): Promise<Pago> {
    // RF-7.6: Idempotencia - Verificamos si la orden ya fue procesada
    const transaccionExistente = await this.pagoRepository.findOne({
      where: { claveIdempotencia: dto.clave_idempotencia }
    });

    if (transaccionExistente) {
      // Si la red se corta y M6 reintenta el cobro, devolvemos el éxito anterior en lugar de cobrar de nuevo
      return transaccionExistente; 
    }

    // RF-7.8: Liquidación al conductor (ej. el conductor se lleva el 80% del cobro de un viaje)
    let montoConductor = 0;
    if (dto.tipo_operacion === 'COBRO_VIAJE') {
      montoConductor = dto.monto * 0.8; 
    }

    // RF-7.3 / RF-7.4: Simulamos la autorización exitosa en la pasarela de pagos
    const estadoTransaccion = 'APROBADO'; 

    const nuevoPago = this.pagoRepository.create({
      idViaje: dto.id_viaje,
      idCliente: dto.id_cliente,
      monto: dto.monto,
      montoConductor: montoConductor,
      estado: estadoTransaccion,
      tipoOperacion: dto.tipo_operacion,
      claveIdempotencia: dto.clave_idempotencia,
    });

    // RF-7.7: Se guarda el registro en el historial financiero
    return this.pagoRepository.save(nuevoPago);
  }

  async obtenerHistorial(idCliente: string): Promise<Pago[]> {
    return this.pagoRepository.find({ where: { idCliente } });
  }
}