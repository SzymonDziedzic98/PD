/***
* Name: Hall with Adrenaline and Cortisol + Path Aversion
* Author: Mikołaj Szurlej; Maciej Kamiński (mod: stress->route feedback)
* Description: Phantom develops a soft, probabilistic aversion to path
*              segments where it experienced fear. Aversion biases route
*              choice via dynamic edge weights; it does NOT hard-block paths.
*              aversion_strength = 0.0 reproduces the original baseline model.
* Tags: ABM, proxemics, feedback, route choice
***/

model Hall_AC

global {

    string roads_file <- "Staszica_SHP_sciezki_01.shp";
	file shape_file_roads <- file(roads_file);

   	string obstacle_file <- "Staszica_SHP_krzaki_09.shp";
	file shape_file_obstacles <- file(obstacle_file);

    geometry shape <- envelope(shape_file_roads);
    graph road_network;
    float step <- 0.005 #mn;
    int number_of_flags <- 0;

	float hall_multiplier <- 4.0;

	float intimate   <-  0.45* hall_multiplier;
	float personal <-  1.2 * hall_multiplier;
	float social <-  3.6 * hall_multiplier;
	float public <- 10.0 * hall_multiplier;

	// >>> FEEDBACK: globalne parametry awersji <<<
	// Siła awersji: 0.0 = brak (model identyczny z oryginałem), wyższe = silniejsze unikanie.
	// To jest Twoja zmienna eksperymentalna (odpowiednik "beta" z koncepcji).
	float aversion_strength <- 5.0;
	// Ile "strachu" odkłada się na odcinku, gdy phantom przekroczy próg lęku w danym cyklu.
	float fear_deposit <- 1.0;
	// Tempo zanikania pamięci strachu na odcinku (na cykl). 1.0 = brak zanikania.
	float fear_decay <- 0.999;
	// Co ile cykli przeliczamy graf (przeliczanie co cykl jest kosztowne).
	int reweight_every <- 20;
	// <<< FEEDBACK

	// Boty chodzą po grafie bez wag strachu (nie znają uczuć phantoma). false = dawne zachowanie: boty na grafie ważonym.
	bool bots_plain_graph <- true;
	graph bot_network;
	// Pamięć strachu: false = wspólna na odcinku dla wszystkich phantomów, true = osobna dla każdego phantoma.
	// Przy jednym phantomie oba warianty dają to samo.
	bool individual_fear <- false;
	// goto w GAMA traktuje wagi grafu także jako koszt RUCHU: na odcinku o wadze 10 × długość agent idzie 10× wolniej.
	// Przy awersji phantom zwalniał więc na odcinkach, na których się bał, zostawał w pobliżu źródła strachu i odkładał
	// kolejny strach (sprzężenie zwrotne; część phantomów prawie stawała). true = ruch z prędkością liczoną po długości,
	// wagi strachu służą tylko do wyboru trasy (jak w porcie Pythona). false = dawne zachowanie.
	bool move_by_length <- true;
	map<road, float> length_weights;

	reflex stop_after_steps {
        if (cycle >= 10000) {
           	ask phantom{
           		do die;
           	}
           	ask bot{
           		do die;
           	}
           	do pause;
        }
    }

	int phantom_nb <- 1;
	int bot_nb <- 80;

    init {
    	create from: shape_file_obstacles species: obstacle  ;
        create road from: shape_file_roads ;
        create bot number: bot_nb {
        	speed <- 4 #km/#h + gauss(0,0.3);
			location <- any_location_in( one_of(road) );
			target <- location;
			shape <- triangle(5);
        }
        create phantom number: phantom_nb {
        	speed <- 4 #km/#h ;
			location <- any_location_in(one_of(road));
			target <- location;
			shape <- triangle(10);
		}

		// >>> FEEDBACK: graf z wagami zależnymi od pamięci strachu <<<
		// weights: dla każdej krawędzi (road) waga = długość * (1 + aversion_strength * fear_memory).
		// Przy fear_memory = 0 wszędzie -> waga = długość -> identyczny routing jak w oryginale.
		bot_network <- as_edge_graph(road);
		length_weights <- road as_map (each::each.shape.perimeter);
		do rebuild_graph;
		// <<< FEEDBACK
    }

	// >>> FEEDBACK: przebudowa ważonego grafu <<<
	action rebuild_graph {
		map<road, float> weights <- road as_map (each:: (each.shape.perimeter * (1.0 + aversion_strength * each.fear_memory)));
		road_network <- as_edge_graph(road) with_weights weights;
		if (individual_fear) {
			ask phantom {
				map<road, float> w <- road as_map (each:: (each.shape.perimeter * (1.0 + aversion_strength * ((my_fear contains_key each) ? my_fear[each] : 0.0))));
				my_network <- as_edge_graph(road) with_weights w;
			}
		}
	}

	// Okresowa aktualizacja: zanikanie strachu na wszystkich odcinkach + przeliczenie grafu.
	reflex update_aversion when: (cycle mod reweight_every) = 0 {
		ask road {
			fear_memory <- fear_memory * fear_decay;
		}
		ask phantom {
			loop r over: my_fear.keys {
				my_fear[r] <- my_fear[r] * fear_decay;
			}
		}
		do rebuild_graph;
	}
	// <<< FEEDBACK

    reflex save_results when: cycle = 9999 {
    ask phantom {
        save [
            myself.bot_nb,
            myself.phantom_nb,
            total_adrenaline,
            total_cortisol,
            total_vigilance
        ]
        rewrite: false
        to: "results/summary.csv"
        header: ["bot_nb", "phantom_nb", "total_adrenaline", "total_cortisol", "total_vigilance"];
    }
}

}
species obstacle {
	aspect default {
		draw shape color: rgb(0,255,0) at: location ;
	}
}

species bot skills: [moving] {
	point target;

	reflex normal_move {
		if ((target distance_to location)<1) {
			target <- any_location_in(one_of(road));
		}
		else {
			if (move_by_length) {
				do goto target: target on: (bots_plain_graph ? bot_network : road_network) move_weights: length_weights;
			} else {
				do goto target: target on: (bots_plain_graph ? bot_network : road_network);
			}
		}
	}

	aspect default {
		draw shape rotate: heading + 90 color: #brown;
	}
}

species fear {
	float transparency;
	aspect default {
    	draw circle(10) color: rgb(255, 0, 0, int(transparency));
	}
}

species phantom skills: [moving] {

   float total_adrenaline <- 0.0;
    float total_cortisol   <- 0.0;
    float total_vigilance  <- 0.0;

   point target;
   // własna pamięć strachu i graf (tylko przy individual_fear = true)
   map<road, float> my_fear <- [];
   graph my_network;

   float vigilance <- 0.5;
   float adrenaline <- 0.5;
   float cortisol <- 0.5;

   float adrenaline_cooldown <- 0.99;
   float cortisol_cooldown <- 0.999;

   list<int> where_are_they <- [];
   list<int> where_were_they <- [];

   geometry public_perception_geometry  update: circle(public, location)  masked_by obstacle;
   geometry social_perception_geometry  update: circle(social, location)  masked_by obstacle;
   geometry personal_perception_geometry  update: circle(personal, location)  masked_by obstacle;
   geometry intimate_perception_geometry    update: circle(intimate, location)    masked_by obstacle;

   reflex update_psychophysiology {
      where_are_they <- bot collect distance_number(each.location);

      cortisol <- cortisol * cortisol_cooldown;
      cortisol <- cortisol + 0.2*adrenaline / ((cortisol + 1.0)*(cortisol + 1.0));

      vigilance <- required_vigilance();

      adrenaline <- adrenaline * adrenaline_cooldown;
      adrenaline <- adrenaline + vigilance;

      where_were_they <- where_are_they;
      if (adrenaline > 11.5) {
    	if (empty(fear at_distance 8)) {
        	create fear {
           		location <- myself.location;
            	transparency <- int(min(255.0, 255.0 * myself.adrenaline / 20.0));
      		}
   		}

   		// >>> FEEDBACK: odłóż strach na NAJBLIŻSZYM odcinku ścieżki <<<
   		// To jest "ślad" — odcinek, na którym phantom się przestraszył,
   		// staje się mniej atrakcyjny przy przyszłym wyborze trasy.
   		road scared_road <- road closest_to self;
   		if (scared_road != nil) {
   			scared_road.fear_memory <- scared_road.fear_memory + fear_deposit;
   			if (individual_fear) {
   				my_fear[scared_road] <- ((my_fear contains_key scared_road) ? my_fear[scared_road] : 0.0) + fear_deposit;
   			}
   		}
   		// <<< FEEDBACK
   	}
   	total_adrenaline <- total_adrenaline + adrenaline;
        total_cortisol   <- total_cortisol   + cortisol;
        total_vigilance  <- total_vigilance  + vigilance;
}

   int distance_number(geometry loc) {
      if (intimate_perception_geometry covers loc)     { return 4; }
      if (personal_perception_geometry covers loc)   { return 3; }
      if (social_perception_geometry covers loc)   { return 2; }
      if (public_perception_geometry covers loc)   { return 1; }
      return 0;
   }

   float required_vigilance {
      if (length(where_were_they) = 0) {
         return 0.0;
      }
      float total <- 0.0;
      loop i from: 0 to: (length(where_are_they) - 1) {
         if (where_were_they[i] < where_are_they[i]) {
            int diff <- where_are_they[i] - where_were_they[i];
            total <- total + (diff * diff - 0.99);
         }
      }
      return total;
   }

	// >>> FEEDBACK: routing po WAŻONYM grafie <<<
	// goto z parametrem on: road_network (ważony) -> phantom wybiera trasę
	// minimalizującą sumę wag, czyli unika odcinków o wysokim fear_memory.
	// Mechanika ruchu i losowania celu pozostaje bez zmian.
	reflex normal_move {
		if ((target distance_to location)<1) {
			target <- any_location_in(one_of(road));
		}
		else {
			if (move_by_length) {
				do goto target: target on: (individual_fear ? my_network : road_network) move_weights: length_weights;
			} else {
				do goto target: target on: (individual_fear ? my_network : road_network);
			}
		}
	}
	// <<< FEEDBACK

	aspect hall {
    	draw public_perception_geometry color: blend(#brown, #blue, 0.3) ;
	}
	aspect hall2 {
    	draw social_perception_geometry color: blend(#brown, #blue, 0.8) ;
	}
	aspect default {
		draw shape rotate: heading + 90 color: #blue;
	}
}

species road {
    rgb color <- rgb(0,0,0) ;

	// >>> FEEDBACK: pamięć strachu na odcinku <<<
	float fear_memory <- 0.0;
	// <<< FEEDBACK

    aspect default {
    	// >>> FEEDBACK: wizualizacja awersji — im więcej strachu, tym bardziej czerwony odcinek <<<
    	draw shape color: rgb(int(min(255.0, 40.0 + fear_memory * 30.0)), 0, 0) width: 2.0;
    	// <<< FEEDBACK
	}
}

experiment Hall  type: gui {
	parameter "liczba phantomów" var: phantom_nb;
	parameter "liczba botów" var: bot_nb;
	parameter "distance intimate" var: intimate;
	parameter "distance personal" var: personal;
	parameter "distance social" var: social;
	parameter "distance public" var: public;
	parameter "Obstacle file" var: obstacle_file;
	parameter "Road file" var: roads_file;
	// >>> FEEDBACK: parametry awersji dostępne w GUI <<<
	parameter "Siła awersji (0 = baseline)" var: aversion_strength;
	parameter "Depozyt strachu" var: fear_deposit;
	parameter "Zanikanie strachu" var: fear_decay;
	parameter "Boty na grafie bez wag strachu" var: bots_plain_graph;
	parameter "Osobna pamięć strachu phantomów" var: individual_fear;
	parameter "Prędkość po długości (wagi tylko do trasy)" var: move_by_length;
	// <<< FEEDBACK

    output {
        display city_display autosave: cycle=10000 type:opengl {
   	        species road  refresh: true;   // >>> FEEDBACK: było false; true, by widzieć narastającą awersję
   	        species obstacle refresh: false;
   	        species phantom aspect: hall;
   	        species phantom aspect: hall2;
   	        species phantom aspect: default;
   	        species bot;
   	        species fear;
   	    }
   	    display chart type:2d refresh:every(1#cycle) {
			chart "Data" memorize: false y_range:{-0.1,55} type: series {
				data "adrenaline" value: phantom[0].adrenaline color:#blue;
				data "kortyzol" value: phantom[0].cortisol color: #purple;
				data "vigilance" value: phantom[0].vigilance color: rgb(0,0,0);
				}
			}
    }
}
