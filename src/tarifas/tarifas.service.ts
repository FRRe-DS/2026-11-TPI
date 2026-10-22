import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { TarifaEstimada } from './entities/tarifa-estimada.entity';
import { CreateTarifaDto } from './dto/create-tarifa.dto';

@Injectable()
export class TarifasService {
  constructor(
    @InjectRepository(TarifaEstimada)
    private tarifaRepository: Repository<TarifaEstimada>,
  ) {}

  async estimarTarifa(createTarifaDto: CreateTarifaDto): Promise<TarifaEstimada> {
    // Parámetros configurables según RF-7.1
    let precioBase = createTarifaDto.tipo_vehiculo.toUpperCase() === 'MOTO' ? 500 : 1000;
    const precioPorKm = createTarifaDto.tipo_vehiculo.toUpperCase() === 'MOTO' ? 80 : 150;
    const precioPorMinuto = 50;

    const montoEstimado = 
      precioBase + 
      (createTarifaDto.distancia_km * precioPorKm) + 
      (createTarifaDto.tiempo_minutos * precioPorMinuto);

    const nuevaTarifa = this.tarifaRepository.create({
      idReserva: createTarifaDto.id_reserva,
      tipoVehiculo: createTarifaDto.tipo_vehiculo,
      distanciaKm: createTarifaDto.distancia_km,
      tiempoMinutos: createTarifaDto.tiempo_minutos,
      montoEstimado: montoEstimado,
    });

    return this.tarifaRepository.save(nuevaTarifa);
  }

  async obtenerTodas(): Promise<TarifaEstimada[]> {
    return this.tarifaRepository.find();
  }
}