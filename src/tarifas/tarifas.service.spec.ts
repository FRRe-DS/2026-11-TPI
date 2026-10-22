import { Test, TestingModule } from '@nestjs/testing';
import { TarifasService } from './tarifas.service';
import { getRepositoryToken } from '@nestjs/typeorm';
import { TarifaEstimada } from './entities/tarifa-estimada.entity';
import { jest } from '@jest/globals';

describe('TarifasService', () => {
  let service: TarifasService;

  // Simulamos el repositorio de TypeORM
  const mockTarifaRepository = {
    create: jest.fn().mockImplementation((dto) => dto),
    save: jest.fn().mockImplementation((tarifa) => Promise.resolve({ id: 1, ...tarifa })),
    find: jest.fn().mockResolvedValue([]),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TarifasService,
        {
          provide: getRepositoryToken(TarifaEstimada),
          useValue: mockTarifaRepository,
        },
      ],
    }).compile();

    service = module.get<TarifasService>(TarifasService);
  });

  it('debería calcular el monto correctamente al estimar', async () => {
    const dto = { id_reserva: 'res-test', distancia_km: 10, tiempo_minutos: 15, tipo_vehiculo: 'AUTO' };
    
    // Cálculo esperado: 1000 + (10 * 150) + (15 * 50) = 3250
    const resultado = await service.estimarTarifa(dto);
    
    expect(resultado.montoEstimado).toEqual(3250);
    expect(resultado.idReserva).toEqual('res-test');
  });
});