import { Test, TestingModule } from '@nestjs/testing';
import { TarifasController } from './tarifas.controller';
import { TarifasService } from './tarifas.service';

describe('TarifasController', () => {
  let controller: TarifasController;
  let service: TarifasService;

  const mockTarifasService = {
    estimarTarifa: jest.fn((dto) => {
      return {
        id: 1,
        idReserva: dto.id_reserva,
        montoEstimado: 3250,
      };
    }),
    obtenerTodas: jest.fn(() => []),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [TarifasController],
      providers: [
        {
          provide: TarifasService,
          useValue: mockTarifasService,
        },
      ],
    }).compile();

    controller = module.get<TarifasController>(TarifasController);
    service = module.get<TarifasService>(TarifasService);
  });

  it('debería llamar al servicio para estimar tarifa mediante el POST', async () => {
    const dto = { id_reserva: 'res-test', distancia_km: 10, tiempo_minutos: 15 };
    const resultado = await controller.estimar(dto);

    expect(service.estimarTarifa).toHaveBeenCalledWith(dto);
    expect(resultado.idReserva).toEqual('res-test');
  });
});